#!/bin/sh
# Builds SHOW.EXE (i386 Win32, Windows 95 compatible) with clang + lld-link. No SDK needed.
set -eu
cd "$(dirname "$0")"
OUT=${1:-../build/SHOW.EXE}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# import libraries from the functions show.c actually uses (stdcall: name@argbytes)
cat > "$TMP/kernel32.def" <<'EOF'
LIBRARY KERNEL32.dll
EXPORTS
GetModuleFileNameA@12
GetModuleHandleA@4
ExitProcess@4
CreateMutexA@12
GetLastError@0
CreateFileA@28
ReadFile@20
WriteFile@20
SetCommTimeouts@8
GetPrivateProfileStringA@24
GetPrivateProfileIntA@16
GetFileAttributesA@4
Sleep@4
EOF
cat > "$TMP/user32.def" <<'EOF'
LIBRARY USER32.dll
EXPORTS
RegisterClassA@4
CreateWindowExA@48
ShowWindow@8
UpdateWindow@4
GetMessageA@16
TranslateMessage@4
DispatchMessageA@4
DefWindowProcA@16
PostQuitMessage@4
InvalidateRect@12
BeginPaint@8
EndPaint@8
GetDC@4
ReleaseDC@8
GetSystemMetrics@4
LoadImageA@24
ShowCursor@4
SetTimer@16
FindWindowA@8
SetForegroundWindow@4
FillRect@12
DrawTextA@20
EOF
cat > "$TMP/gdi32.def" <<'EOF'
LIBRARY GDI32.dll
EXPORTS
CreateCompatibleDC@4
CreateCompatibleBitmap@12
SelectObject@8
DeleteDC@4
DeleteObject@4
StretchBlt@44
BitBlt@36
SetStretchBltMode@8
GetObjectA@12
GetStockObject@4
SetTextColor@8
SetBkMode@8
EOF
for l in kernel32 user32 gdi32; do
  llvm-dlltool -m i386 -k -d "$TMP/$l.def" -l "$TMP/$l.lib"
done

clang -target i386-pc-windows-msvc -march=pentium -Os -ffreestanding -fno-builtin \
  -fno-stack-protector -mno-stack-arg-probe -Wall -Wno-unused-function \
  -c show.c -o "$TMP/show.obj"

mkdir -p "$(dirname "$OUT")"
lld-link /nologo /entry:start /subsystem:windows,4.0 /nodefaultlib /fixed:no \
  /opt:ref /merge:.rdata=.text /out:"$OUT" "$TMP/show.obj" \
  "$TMP/kernel32.lib" "$TMP/user32.lib" "$TMP/gdi32.lib"

python3 fix_pe.py "$OUT"
