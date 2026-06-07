import sys
import time

import win32gui
import win32ui
import win32con
from ctypes import windll
from PIL import Image


def shoot(title_substr: str, out_path: str):
    hwnd = None
    def cb(h, _):
        nonlocal hwnd
        if win32gui.IsWindowVisible(h) and title_substr.lower() in win32gui.GetWindowText(h).lower():
            hwnd = h
    win32gui.EnumWindows(cb, None)
    if hwnd is None:
        print("window not found")
        sys.exit(1)

    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width, height = right - left, bottom - top
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)
    windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)

    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    print("bmpinfo", bmpinfo, "len", len(bmpstr), "expected", bmpinfo["bmWidth"] * bmpinfo["bmHeight"] * 4)
    w, h = bmpinfo["bmWidth"], bmpinfo["bmHeight"]
    img = Image.frombuffer("RGB", (w, len(bmpstr) // (w * 4)), bmpstr, "raw", "BGRX", 0, 1)
    img.save(out_path)

    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    print("saved", out_path)


if __name__ == "__main__":
    shoot(sys.argv[1], sys.argv[2])
