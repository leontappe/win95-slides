/*
 * SHOW.EXE - fullscreen slideshow for Windows 95 (and later).
 * Shows SLIDE001.BMP.. from its own folder, configured by DECK.INI.
 * Talks to the host page over COM1: sends "HELLO n", "SLIDE i n";
 * accepts n/p/h/e (next/prev/home/end), g<num>; (goto), b (black), q (quit).
 * No CRT: built with clang + lld-link against kernel32/user32/gdi32 only.
 */
#include "w32.h"

#define CLASS_NAME "Win95SlideShow"
#define MAX_SLIDES 999

enum { T_NONE, T_WIPE, T_BLINDS, T_BOX, T_DISSOLVE };

static HWND g_wnd;
static int g_w, g_h;
static char g_dir[MAX_PATH], g_ini[MAX_PATH];
static int g_count, g_cur = -1, g_blank; /* g_blank: 0 off, 1 black, 2 white */
static int g_default_trans;
static HDC g_back_dc;
static HANDLE g_com = INVALID_HANDLE_VALUE;
static int g_num, g_num_len;   /* typed slide number (PowerPoint-style "12 Enter") */
static int g_rx_goto, g_rx_num; /* serial "g<num>;" parser */

/* clang may emit these for struct copies/zeroing */
void *memset(void *d, int c, unsigned n) { BYTE *p = d; while (n--) *p++ = (BYTE)c; return d; }
void *memcpy(void *d, const void *s, unsigned n) { BYTE *p = d; const BYTE *q = s; while (n--) *p++ = *q++; return d; }

static int str_len(const char *s) { int n = 0; while (s[n]) n++; return n; }
static char *str_cpy(char *d, const char *s) { while ((*d = *s++)) d++; return d; }
static char *int_to_str(char *d, int v)
{
    char t[12]; int n = 0;
    if (v < 0) { *d++ = '-'; v = -v; }
    do { t[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    while (n) *d++ = t[--n];
    *d = 0;
    return d;
}
static int lower(int c) { return (c >= 'A' && c <= 'Z') ? c + 32 : c; }
static int str_ieq(const char *a, const char *b)
{
    while (*a && lower(*a) == lower(*b)) a++, b++;
    return lower(*a) == lower(*b);
}

static void slide_path(char *out, int idx)
{
    char *p = str_cpy(out, g_dir);
    p = str_cpy(p, "SLIDE");
    *p++ = (char)('0' + (idx + 1) / 100 % 10);
    *p++ = (char)('0' + (idx + 1) / 10 % 10);
    *p++ = (char)('0' + (idx + 1) % 10);
    str_cpy(p, ".BMP");
}

static int parse_trans(const char *s)
{
    if (str_ieq(s, "wipe")) return T_WIPE;
    if (str_ieq(s, "blinds")) return T_BLINDS;
    if (str_ieq(s, "box")) return T_BOX;
    if (str_ieq(s, "dissolve")) return T_DISSOLVE;
    return T_NONE;
}

static int slide_trans(int idx)
{
    char key[8], val[16];
    int_to_str(key, idx + 1);
    GetPrivateProfileStringA("transitions", key, "", val, sizeof val, g_ini);
    return val[0] ? parse_trans(val) : g_default_trans;
}

static void serial_write(const char *s)
{
    DWORD n;
    if (g_com != INVALID_HANDLE_VALUE) WriteFile(g_com, s, str_len(s), &n, NULL);
}

static void report(void)
{
    char buf[40], *p = str_cpy(buf, "SLIDE ");
    p = int_to_str(p, g_cur + 1);
    *p++ = ' ';
    p = int_to_str(p, g_count);
    str_cpy(p, "\r\n");
    serial_write(buf);
}

/* Render slide idx (or the end screen when idx == g_count) into the back buffer. */
static void compose(int idx)
{
    RECT r = { 0, 0, g_w, g_h };
    FillRect(g_back_dc, &r, GetStockObject(BLACK_BRUSH));

    if (idx >= g_count) {
        r.top = 8; r.bottom = 40;
        SelectObject(g_back_dc, GetStockObject(ANSI_VAR_FONT));
        SetBkMode(g_back_dc, TRANSPARENT);
        SetTextColor(g_back_dc, RGB(255, 255, 255));
        DrawTextA(g_back_dc, "End of slide show, press Esc to exit.", -1, &r, DT_CENTER | DT_SINGLELINE);
        return;
    }

    char path[MAX_PATH];
    slide_path(path, idx);
    HBITMAP bmp = LoadImageA(NULL, path, IMAGE_BITMAP, 0, 0, LR_LOADFROMFILE | LR_CREATEDIBSECTION);
    if (!bmp) bmp = LoadImageA(NULL, path, IMAGE_BITMAP, 0, 0, LR_LOADFROMFILE);
    if (!bmp) return;

    BITMAP bm;
    GetObjectA(bmp, sizeof bm, &bm);
    int bh = bm.bmHeight < 0 ? -bm.bmHeight : bm.bmHeight;

    /* fit with preserved aspect ratio */
    int dw = g_w, dh = g_w * bh / bm.bmWidth;
    if (dh > g_h) { dh = g_h; dw = g_h * bm.bmWidth / bh; }
    int dx = (g_w - dw) / 2, dy = (g_h - dh) / 2;

    HDC mem = CreateCompatibleDC(g_back_dc);
    HGDIOBJ old = SelectObject(mem, bmp);
    if (dw == bm.bmWidth && dh == bh) {
        BitBlt(g_back_dc, dx, dy, dw, dh, mem, 0, 0, SRCCOPY);
    } else {
        SetStretchBltMode(g_back_dc, COLORONCOLOR);
        StretchBlt(g_back_dc, dx, dy, dw, dh, mem, 0, 0, bm.bmWidth, bh, SRCCOPY);
    }
    SelectObject(mem, old);
    DeleteDC(mem);
    DeleteObject(bmp);
}

static void blit(HDC dc, int x, int y, int w, int h)
{
    if (w > 0 && h > 0) BitBlt(dc, x, y, w, h, g_back_dc, x, y, SRCCOPY);
}

static int gcd(int a, int b) { while (b) { int t = a % b; a = b; b = t; } return a; }

/* Copy the back buffer to the screen using a transition effect. */
static void present(int trans)
{
    HDC dc = GetDC(g_wnd);
    int i, steps;

    switch (trans) {
    case T_WIPE:
        steps = 20;
        for (i = 0; i < steps; i++) {
            int x0 = g_w * i / steps, x1 = g_w * (i + 1) / steps;
            blit(dc, x0, 0, x1 - x0, g_h);
            Sleep(15);
        }
        break;
    case T_BLINDS: {
        int bands = 8, band = (g_h + bands - 1) / bands;
        steps = 12;
        for (i = 0; i < steps; i++) {
            int y0 = band * i / steps, y1 = band * (i + 1) / steps, b;
            for (b = 0; b < bands; b++) blit(dc, 0, b * band + y0, g_w, y1 - y0);
            Sleep(25);
        }
        break;
    }
    case T_BOX:
        steps = 14;
        for (i = 1; i <= steps; i++) {
            int w = g_w * i / steps, h = g_h * i / steps;
            blit(dc, (g_w - w) / 2, (g_h - h) / 2, w, h);
            Sleep(18);
        }
        break;
    case T_DISSOLVE: {
        int cs = 16, cols = (g_w + cs - 1) / cs, rows = (g_h + cs - 1) / cs, n = cols * rows;
        int step = 7919, batch = n / 16 + 1;
        while (gcd(step, n) != 1) step += 2;
        for (i = 0; i < n; i++) {
            int c = (int)(((unsigned)i * (unsigned)step) % (unsigned)n);
            blit(dc, c % cols * cs, c / cols * cs, cs, cs);
            if (i % batch == batch - 1) Sleep(20);
        }
        break;
    }
    default:
        blit(dc, 0, 0, g_w, g_h);
    }
    ReleaseDC(g_wnd, dc);
}

static void go(int idx)
{
    if (idx < 0) idx = 0;
    if (idx > g_count) idx = g_count;
    if (idx == g_cur && !g_blank) return;
    int forward = idx > g_cur;
    g_blank = 0;
    compose(idx);
    present(forward && idx < g_count ? slide_trans(idx) : T_NONE);
    g_cur = idx;
    report();
}

static void set_blank(int mode)
{
    g_blank = g_blank == mode ? 0 : mode;
    if (!g_blank) { InvalidateRect(g_wnd, NULL, FALSE); return; }
    HDC dc = GetDC(g_wnd);
    RECT r = { 0, 0, g_w, g_h };
    FillRect(dc, &r, GetStockObject(g_blank == 1 ? BLACK_BRUSH : WHITE_BRUSH));
    ReleaseDC(g_wnd, dc);
}

static void handle_command(int c)
{
    if (g_rx_goto) {
        if (c >= '0' && c <= '9') { g_rx_num = g_rx_num * 10 + c - '0'; return; }
        g_rx_goto = 0;
        if (c == ';') { go(g_rx_num - 1); return; }
    }
    switch (c) {
    case 'n': go(g_cur + 1); break;
    case 'p': go(g_cur - 1); break;
    case 'h': go(0); break;
    case 'e': go(g_count - 1); break;
    case 'b': set_blank(1); break;
    case 'w': set_blank(2); break;
    case 'q': PostQuitMessage(0); break;
    case 'g': g_rx_goto = 1; g_rx_num = 0; break;
    case '?': report(); break;
    }
}

static void poll_serial(void)
{
    char buf[64];
    DWORD n, i;
    if (g_com == INVALID_HANDLE_VALUE) return;
    while (ReadFile(g_com, buf, sizeof buf, &n, NULL) && n)
        for (i = 0; i < n; i++) handle_command(buf[i]);
}

static void on_key(WPARAM vk)
{
    int digit = -1;
    if (vk >= '0' && vk <= '9') digit = (int)vk - '0';
    if (vk >= 0x60 && vk <= 0x69) digit = (int)vk - 0x60; /* numpad */
    if (digit >= 0) {
        if (g_num_len < 3) { g_num = g_num * 10 + digit; g_num_len++; }
        return;
    }
    if (vk == VK_RETURN && g_num_len) { go(g_num - 1); g_num = g_num_len = 0; return; }
    g_num = g_num_len = 0;

    switch (vk) {
    case VK_RIGHT: case VK_DOWN: case VK_NEXT: case VK_SPACE: case VK_RETURN: case 'N':
        go(g_cur + 1); break;
    case VK_LEFT: case VK_UP: case VK_PRIOR: case VK_BACK: case 'P':
        go(g_cur - 1); break;
    case VK_HOME: go(0); break;
    case VK_END: go(g_count - 1); break;
    case 'B': case 0xBE: set_blank(1); break; /* B or '.' like PowerPoint */
    case 'W': case 0xBC: set_blank(2); break; /* W or ',' */
    case VK_ESCAPE:
        if (g_blank) set_blank(g_blank);
        else PostQuitMessage(0);
        break;
    }
}

static LRESULT WINAPI wnd_proc(HWND w, UINT m, WPARAM wp, LPARAM lp)
{
    switch (m) {
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(w, &ps);
        if (g_blank) FillRect(dc, &ps.rcPaint, GetStockObject(g_blank == 1 ? BLACK_BRUSH : WHITE_BRUSH));
        else blit(dc, ps.rcPaint.left, ps.rcPaint.top, ps.rcPaint.right - ps.rcPaint.left, ps.rcPaint.bottom - ps.rcPaint.top);
        EndPaint(w, &ps);
        return 0;
    }
    case WM_ERASEBKGND: return 1;
    case WM_KEYDOWN: on_key(wp); return 0;
    case WM_LBUTTONDOWN: go(g_cur + 1); return 0;
    case WM_RBUTTONDOWN: go(g_cur - 1); return 0;
    case WM_TIMER: poll_serial(); return 0;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    }
    return DefWindowProcA(w, m, wp, lp);
}

static void open_serial(void)
{
    COMMTIMEOUTS t = { 0xFFFFFFFF, 0, 0, 0, 200 }; /* reads return immediately */
    g_com = CreateFileA("COM1", GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL);
    if (g_com != INVALID_HANDLE_VALUE) SetCommTimeouts(g_com, &t);
}

static int run(void)
{
    HINSTANCE inst = GetModuleHandleA(NULL);

    /* a second launch (autorun + Run dialog) just brings the first to front */
    CreateMutexA(NULL, FALSE, "Win95SlideShowMutex");
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        HWND other = FindWindowA(CLASS_NAME, NULL);
        if (other) SetForegroundWindow(other);
        return 0;
    }

    GetModuleFileNameA(NULL, g_dir, MAX_PATH);
    int i = str_len(g_dir);
    while (i > 0 && g_dir[i - 1] != '\\') i--;
    g_dir[i] = 0;
    str_cpy(str_cpy(g_ini, g_dir), "DECK.INI");

    char val[16];
    GetPrivateProfileStringA("deck", "transition", "none", val, sizeof val, g_ini);
    g_default_trans = parse_trans(val);
    g_count = (int)GetPrivateProfileIntA("deck", "slides", 0, g_ini);
    if (g_count <= 0) { /* no INI: probe for files */
        char path[MAX_PATH];
        for (g_count = 0; g_count < MAX_SLIDES; g_count++) {
            slide_path(path, g_count);
            if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) break;
        }
    }
    if (g_count <= 0) return 1;

    g_w = GetSystemMetrics(SM_CXSCREEN);
    g_h = GetSystemMetrics(SM_CYSCREEN);

    WNDCLASSA wc = { 0 };
    wc.lpfnWndProc = wnd_proc;
    wc.hInstance = inst;
    wc.hbrBackground = GetStockObject(BLACK_BRUSH);
    wc.lpszClassName = CLASS_NAME;
    RegisterClassA(&wc);

    g_wnd = CreateWindowExA(WS_EX_TOPMOST, CLASS_NAME, "Slide Show", WS_POPUP | WS_VISIBLE,
                            0, 0, g_w, g_h, NULL, NULL, inst, NULL);
    if (!g_wnd) return 1;

    HDC dc = GetDC(g_wnd);
    g_back_dc = CreateCompatibleDC(dc);
    SelectObject(g_back_dc, CreateCompatibleBitmap(dc, g_w, g_h));
    ReleaseDC(g_wnd, dc);

    ShowCursor(FALSE);
    SetForegroundWindow(g_wnd);
    open_serial();
    {
        char buf[24], *p = str_cpy(buf, "HELLO ");
        str_cpy(int_to_str(p, g_count), "\r\n");
        serial_write(buf);
    }
    go(0);
    SetTimer(g_wnd, 1, 50, NULL);

    MSG msg;
    while (GetMessageA(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageA(&msg);
    }
    serial_write("BYE\r\n");
    ShowCursor(TRUE);
    return 0;
}

void WINAPI start(void) { ExitProcess((UINT)run()); }
