# Keyboard Language Switcher

A Windows utility to automatically switch the input language based on the connected keyboard's hardware ID (HWID). Includes a GUI tool to list and copy keyboard HWIDs for configuration.

## Features
- Detects connected keyboards and their HWIDs
- Automatically switches Windows input language when a specific keyboard is connected
- Simple GUI to list and copy keyboard HWIDs

## Requirements
- Python 3.8+
- [pywinusb](https://pypi.org/project/pywinusb/)
- [wmi](https://pypi.org/project/WMI/)
- [tkinter](https://docs.python.org/3/library/tkinter.html) (standard library)

## Installation
```bash
pip install pywinusb wmi
```

## Usage
### 1. List and Copy Keyboard HWIDs
Run the following script to open a GUI that lists all connected keyboards and allows you to copy their HWIDs:

```bash
python keyboard_hwid.py
```

### 2. Automatic Language Switching
Edit the `keyboard_config` dictionary in `main.py` to add your keyboards and desired input layouts. Example:

```python
keyboard_config = {
    "NuphyKick75": {
        "vid_pid": ["VID_19F5&PID_3247", "VID_19F5&PID_32D5"],
        "layout": "00000409"  # en-US
    },
    "KeychronV1Max": {
        "vid_pid": ["VID_3434&PID_0914", "VID_3434&PID_D030"],
        "layout": "0000040C"  # fr-FR
    }
}
```

Run the script:
```bash
python main.py
```

The script will monitor connected keyboards and switch the input language automatically.

## Packaging (Optional)
To create a standalone executable (requires [PyInstaller](https://pyinstaller.org/)):
```bash
pyinstaller --noconsole --onefile --hidden-import=wmi --hidden-import=pyautogui main.py
```

## License
MIT License 
