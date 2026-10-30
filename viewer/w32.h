/* Minimal Win32 declarations for SHOW.EXE (no SDK, no CRT, i386 stdcall). */
#pragma once
typedef unsigned int UINT; typedef unsigned long DWORD; typedef int BOOL; typedef long LONG;
typedef unsigned short WORD; typedef unsigned char BYTE; typedef void *HANDLE;
typedef HANDLE HWND, HINSTANCE, HDC, HBITMAP, HBRUSH, HICON, HCURSOR, HMENU, HGDIOBJ, HFONT;
typedef UINT WPARAM; typedef LONG LPARAM, LRESULT; typedef DWORD COLORREF;
#define WINAPI __stdcall
#define NULL ((void *)0)
#define TRUE 1
#define FALSE 0
#define MAX_PATH 260
#define RGB(r, g, b) ((COLORREF)((r) | ((g) << 8) | ((b) << 16)))

typedef LRESULT(WINAPI *WNDPROC)(HWND, UINT, WPARAM, LPARAM);
typedef struct { LONG left, top, right, bottom; } RECT;
typedef struct { LONG x, y; } POINT;
typedef struct { UINT style; WNDPROC lpfnWndProc; int cbClsExtra, cbWndExtra; HINSTANCE hInstance;
    HICON hIcon; HCURSOR hCursor; HBRUSH hbrBackground; const char *lpszMenuName, *lpszClassName; } WNDCLASSA;
typedef struct { HWND hwnd; UINT message; WPARAM wParam; LPARAM lParam; DWORD time; POINT pt; } MSG;
typedef struct { HDC hdc; BOOL fErase; RECT rcPaint; BOOL fRestore, fIncUpdate; BYTE rgbReserved[32]; } PAINTSTRUCT;
typedef struct { LONG bmType, bmWidth, bmHeight, bmWidthBytes; WORD bmPlanes, bmBitsPixel; void *bmBits; } BITMAP;
typedef struct { DWORD ReadIntervalTimeout, ReadTotalTimeoutMultiplier, ReadTotalTimeoutConstant,
    WriteTotalTimeoutMultiplier, WriteTotalTimeoutConstant; } COMMTIMEOUTS;

/* kernel32 */
__declspec(dllimport) DWORD WINAPI GetModuleFileNameA(HINSTANCE, char *, DWORD);
__declspec(dllimport) HINSTANCE WINAPI GetModuleHandleA(const char *);
__declspec(dllimport) void WINAPI ExitProcess(UINT);
__declspec(dllimport) HANDLE WINAPI CreateMutexA(void *, BOOL, const char *);
__declspec(dllimport) DWORD WINAPI GetLastError(void);
__declspec(dllimport) HANDLE WINAPI CreateFileA(const char *, DWORD, DWORD, void *, DWORD, DWORD, HANDLE);
__declspec(dllimport) BOOL WINAPI ReadFile(HANDLE, void *, DWORD, DWORD *, void *);
__declspec(dllimport) BOOL WINAPI WriteFile(HANDLE, const void *, DWORD, DWORD *, void *);
__declspec(dllimport) BOOL WINAPI SetCommTimeouts(HANDLE, COMMTIMEOUTS *);
__declspec(dllimport) DWORD WINAPI GetPrivateProfileStringA(const char *, const char *, const char *, char *, DWORD, const char *);
__declspec(dllimport) UINT WINAPI GetPrivateProfileIntA(const char *, const char *, int, const char *);
__declspec(dllimport) DWORD WINAPI GetFileAttributesA(const char *);
__declspec(dllimport) void WINAPI Sleep(DWORD);
/* user32 */
__declspec(dllimport) WORD WINAPI RegisterClassA(const WNDCLASSA *);
__declspec(dllimport) HWND WINAPI CreateWindowExA(DWORD, const char *, const char *, DWORD, int, int, int, int, HWND, HMENU, HINSTANCE, void *);
__declspec(dllimport) BOOL WINAPI ShowWindow(HWND, int);
__declspec(dllimport) BOOL WINAPI UpdateWindow(HWND);
__declspec(dllimport) BOOL WINAPI GetMessageA(MSG *, HWND, UINT, UINT);
__declspec(dllimport) BOOL WINAPI TranslateMessage(const MSG *);
__declspec(dllimport) LRESULT WINAPI DispatchMessageA(const MSG *);
__declspec(dllimport) LRESULT WINAPI DefWindowProcA(HWND, UINT, WPARAM, LPARAM);
__declspec(dllimport) void WINAPI PostQuitMessage(int);
__declspec(dllimport) BOOL WINAPI InvalidateRect(HWND, const RECT *, BOOL);
__declspec(dllimport) HDC WINAPI BeginPaint(HWND, PAINTSTRUCT *);
__declspec(dllimport) BOOL WINAPI EndPaint(HWND, const PAINTSTRUCT *);
__declspec(dllimport) HDC WINAPI GetDC(HWND);
__declspec(dllimport) int WINAPI ReleaseDC(HWND, HDC);
__declspec(dllimport) int WINAPI GetSystemMetrics(int);
__declspec(dllimport) HANDLE WINAPI LoadImageA(HINSTANCE, const char *, UINT, int, int, UINT);
__declspec(dllimport) int WINAPI ShowCursor(BOOL);
__declspec(dllimport) UINT WINAPI SetTimer(HWND, UINT, UINT, void *);
__declspec(dllimport) HWND WINAPI FindWindowA(const char *, const char *);
__declspec(dllimport) BOOL WINAPI SetForegroundWindow(HWND);
__declspec(dllimport) int WINAPI FillRect(HDC, const RECT *, HBRUSH);
__declspec(dllimport) int WINAPI DrawTextA(HDC, const char *, int, RECT *, UINT);
/* gdi32 */
__declspec(dllimport) HDC WINAPI CreateCompatibleDC(HDC);
__declspec(dllimport) HBITMAP WINAPI CreateCompatibleBitmap(HDC, int, int);
__declspec(dllimport) HGDIOBJ WINAPI SelectObject(HDC, HGDIOBJ);
__declspec(dllimport) BOOL WINAPI DeleteDC(HDC);
__declspec(dllimport) BOOL WINAPI DeleteObject(HGDIOBJ);
__declspec(dllimport) BOOL WINAPI StretchBlt(HDC, int, int, int, int, HDC, int, int, int, int, DWORD);
__declspec(dllimport) BOOL WINAPI BitBlt(HDC, int, int, int, int, HDC, int, int, DWORD);
__declspec(dllimport) int WINAPI SetStretchBltMode(HDC, int);
__declspec(dllimport) int WINAPI GetObjectA(HGDIOBJ, int, void *);
__declspec(dllimport) HGDIOBJ WINAPI GetStockObject(int);
__declspec(dllimport) COLORREF WINAPI SetTextColor(HDC, COLORREF);
__declspec(dllimport) int WINAPI SetBkMode(HDC, int);

#define GENERIC_READ 0x80000000
#define GENERIC_WRITE 0x40000000
#define OPEN_EXISTING 3
#define INVALID_HANDLE_VALUE ((HANDLE)-1)
#define INVALID_FILE_ATTRIBUTES 0xFFFFFFFF
#define ERROR_ALREADY_EXISTS 183
#define WS_POPUP 0x80000000
#define WS_VISIBLE 0x10000000
#define WS_EX_TOPMOST 0x00000008
#define SW_SHOW 5
#define SM_CXSCREEN 0
#define SM_CYSCREEN 1
#define IMAGE_BITMAP 0
#define LR_LOADFROMFILE 0x0010
#define LR_CREATEDIBSECTION 0x2000
#define SRCCOPY 0x00CC0020
#define COLORONCOLOR 3
#define BLACK_BRUSH 4
#define WHITE_BRUSH 0
#define DEFAULT_GUI_FONT 17
#define ANSI_VAR_FONT 12
#define TRANSPARENT 1
#define DT_CENTER 1
#define DT_VCENTER 4
#define DT_SINGLELINE 0x20
#define WM_DESTROY 0x0002
#define WM_PAINT 0x000F
#define WM_ERASEBKGND 0x0014
#define WM_SETCURSOR 0x0020
#define WM_KEYDOWN 0x0100
#define WM_CHAR 0x0102
#define WM_TIMER 0x0113
#define WM_LBUTTONDOWN 0x0201
#define WM_RBUTTONDOWN 0x0204
#define VK_BACK 0x08
#define VK_RETURN 0x0D
#define VK_ESCAPE 0x1B
#define VK_SPACE 0x20
#define VK_PRIOR 0x21
#define VK_NEXT 0x22
#define VK_END 0x23
#define VK_HOME 0x24
#define VK_LEFT 0x25
#define VK_UP 0x26
#define VK_RIGHT 0x27
#define VK_DOWN 0x28
