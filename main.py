import re
import wmi
import time
import ctypes

# Windows consts
KLF_ACTIVATE = 0x00000001
HWND_BROADCAST = 0xFFFF
WM_INPUTLANGCHANGEREQUEST = 0x0050

keyboard_config = {
    "NuphyKick75": {
        "vid_pid": [
            "VID_19F5&PID_3247",
            "VID_19F5&PID_32D5"
        ],
        "layout": "00000409"  # en-US
    },
    "KeychronV1Max": {
        "vid_pid": [
            "VID_3434&PID_0914",
            "VID_3434&PID_D030"
        ],
        "layout": "0000040C"  # fr-FR
    }
}

def get_connected_keyboards():
    """
    Returns a list of device IDs for all connected keyboards.
    """
    c = wmi.WMI()
    return [kb.deviceid for kb in c.Win32_Keyboard()]

def extract_vid_pid(deviceid):
    """
    Extracts the VID & PID from a device ID string. Returns as uppercase string or None.
    """
    match = re.search(r'(VID_[0-9A-Fa-f]{4}&PID_[0-9A-Fa-f]{4})', deviceid)
    if match:
        return match.group(1).upper()
    return None

def detect_active_keyboard():
    """
    Detects which configured keyboard is currently connected, based on VID & PID.
    Returns the keyboard name or None if not found.
    """
    connected = get_connected_keyboards()
    connected_vid_pid = [extract_vid_pid(dev_id) for dev_id in connected]
    connected_vid_pid = [x for x in connected_vid_pid if x is not None]

    for name, data in keyboard_config.items():
        for vid_pid in data["vid_pid"]:
            if vid_pid.upper() in connected_vid_pid:
                return name
    return None

def get_current_input_language():
    """
    Returns the current Windows input language as a hex string (e.g., '00000409' for en-US).
    """
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    hkl = user32.GetKeyboardLayout(0)
    lang_id = hkl & 0xFFFF
    return f"{lang_id:08X}"

def force_input_language(layout_hex):
    """
    Forces the Windows input language to the specified layout (hex string).
    """
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    hkl = user32.LoadKeyboardLayoutW(layout_hex, KLF_ACTIVATE)
    if hkl == 0:
        print(f"[ERROR] Failed to switch to layout {layout_hex}.")
    else:
        user32.PostMessageW(HWND_BROADCAST, WM_INPUTLANGCHANGEREQUEST, 0, hkl)
        print(f"[ACTION] Language switched to {layout_hex}.")

def main():
    """
    Main loop: detects active keyboard and switches input language if needed.
    """
    print("[INFO] Keyboard language switcher started.")
    last_keyboard = None

    while True:
        active_keyboard = detect_active_keyboard()
        if active_keyboard and active_keyboard != last_keyboard:
            expected_layout = keyboard_config[active_keyboard]["layout"]
            current_layout = get_current_input_language()
            print(f"[INFO] Active keyboard: {active_keyboard}")
            print(f"[INFO] Current layout: {current_layout} | Expected: {expected_layout}")
            if current_layout != expected_layout:
                force_input_language(expected_layout)
            last_keyboard = active_keyboard
        time.sleep(1)

if __name__ == "__main__":
    main()

# pyinstaller --noconsole --onefile --hidden-import=wmi --hidden-import=pyautogui main.py
