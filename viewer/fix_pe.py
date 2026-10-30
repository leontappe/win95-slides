"""Make a PE loadable on Windows 95: OS/subsystem version 4.0, no NX/ASLR flags, valid checksum.
Fails loudly if it imports anything Windows 95 lacks."""
import sys
import pefile

# Functions present in Windows 95's KERNEL32/USER32/GDI32 (the only ones SHOW.EXE should use).
WIN95_OK = {
    "KERNEL32.dll": {"GetModuleFileNameA", "GetModuleHandleA", "ExitProcess", "CreateMutexA", "GetLastError",
                     "CreateFileA", "ReadFile", "WriteFile", "SetCommTimeouts", "GetPrivateProfileStringA",
                     "GetPrivateProfileIntA", "GetFileAttributesA", "Sleep"},
    "USER32.dll": {"RegisterClassA", "CreateWindowExA", "ShowWindow", "UpdateWindow", "GetMessageA",
                   "TranslateMessage", "DispatchMessageA", "DefWindowProcA", "PostQuitMessage", "InvalidateRect",
                   "BeginPaint", "EndPaint", "GetDC", "ReleaseDC", "GetSystemMetrics", "LoadImageA", "ShowCursor",
                   "SetTimer", "FindWindowA", "SetForegroundWindow", "FillRect", "DrawTextA"},
    "GDI32.dll": {"CreateCompatibleDC", "CreateCompatibleBitmap", "SelectObject", "DeleteDC", "DeleteObject",
                  "StretchBlt", "BitBlt", "SetStretchBltMode", "GetObjectA", "GetStockObject", "SetTextColor",
                  "SetBkMode"},
}

path = sys.argv[1]
pe = pefile.PE(path)
oh = pe.OPTIONAL_HEADER
oh.MajorOperatingSystemVersion, oh.MinorOperatingSystemVersion = 4, 0
oh.MajorSubsystemVersion, oh.MinorSubsystemVersion = 4, 0
oh.DllCharacteristics = 0
pe.FILE_HEADER.TimeDateStamp = 0x30000000  # stable output

bad = []
for entry in pe.DIRECTORY_ENTRY_IMPORT:
    dll = entry.dll.decode()
    for imp in entry.imports:
        name = imp.name.decode() if imp.name else f"#{imp.ordinal}"
        if name not in WIN95_OK.get(dll, set()):
            bad.append(f"{dll}!{name}")
if bad:
    sys.exit("imports not allowed on Win95: " + ", ".join(bad))

oh.CheckSum = pe.generate_checksum()
pe.write(path)
print(f"{path}: {len(pe.__data__)} bytes, subsystem {oh.MajorSubsystemVersion}.{oh.MinorSubsystemVersion}, "
      f"{len(pe.sections)} sections, imports ok")
