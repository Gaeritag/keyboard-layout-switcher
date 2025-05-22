# Keyboard Language Switcher

A Windows utility to automatically switch the input language based on the connected keyboard's hardware ID (HWID). Includes a GUI tool to manage HWIDs for configuration.

## Features
- Detects connected keyboards and their HWIDs
- Automatically switches Windows input language when a specific keyboard is connected
- Simple GUI to manage keyboard layout config

## Requirements
- Python 3.8+
- [pywinusb](https://pypi.org/project/pywinusb/)
- [wmi](https://pypi.org/project/WMI/)
- [tkinter](https://docs.python.org/3/library/tkinter.html) (standard library)

## Installation

### Clone the Repository
```bash
git clone https://github.com/Gaeritag/keyboard-layout-switcher.git
cd keyboard-layout-switcher
```

### Set Up a Virtual Environment
```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage
### 1. Start the switcher
Run the following script to start the program:

```bash
python main.py
```

### 2. Edit your config
To open the GUI and make your own config, go to the tray manager after starting the script, right click on the icon and click 'open web interface'.

## Packaging (Optional)
To create a standalone executable (requires [PyInstaller](https://pyinstaller.org/)):
```bash
pyinstaller --onefile --noconsole --add-data "templates;templates" --paths=venv/Lib/site-packages --hidden-import pythoncom --hidden-import pywinusb.hid main.py
```

## License
MIT License 
