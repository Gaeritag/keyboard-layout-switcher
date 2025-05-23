import re
import wmi
from time import sleep
import ctypes
import pystray
from PIL import Image, ImageDraw
import json
import os
import shutil
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import threading
import signal
import webbrowser
from flask_cors import CORS
import pythoncom
import pywinusb.hid as hid
from collections import deque
from functools import wraps

# Windows consts
KLF_ACTIVATE = 0x00000001
HWND_BROADCAST = 0xFFFF
WM_INPUTLANGCHANGEREQUEST = 0x0050

CONFIG_FILE = "keyboard_config.json"

# Constants for rate limiting and size restrictions
MAX_CONFIG_SIZE = 1024 * 1024  # 1MB max config size
MAX_KEYBOARDS = 50            # Maximum number of keyboards in config
MAX_VID_PID_PER_KEYBOARD = 10 # Maximum VID/PID entries per keyboard
 
# Initialize Flask app
app = Flask(__name__)
CORS(app)
shutdown_event = threading.Event()

def load_config():
    """Load keyboard configuration from file or return empty dict if not exists."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def validate_config(config):
    """Validate the config structure and data types."""
    if not isinstance(config, list):
        return False, "Config must be a list"
    
    # Check total size
    config_str = json.dumps(config)
    if len(config_str.encode('utf-8')) > MAX_CONFIG_SIZE:
        return False, f"Config size exceeds maximum allowed size of {MAX_CONFIG_SIZE/1024/1024}MB"
    
    # Check number of keyboards
    if len(config) > MAX_KEYBOARDS:
        return False, f"Number of keyboards exceeds maximum allowed ({MAX_KEYBOARDS})"
    
    required_fields = ["name", "enabled", "connected", "active", "layout", "product", "vendor", "vid_pid"]
    
    for keyboard in config:
        if not isinstance(keyboard, dict):
            return False, "Each keyboard must be a dictionary"
        
        # Check required fields
        for field in required_fields:
            if field not in keyboard:
                return False, f"Missing required field: {field}"
        
        # Validate field types and lengths
        if not isinstance(keyboard["name"], str) or len(keyboard["name"]) > 100:
            return False, "Keyboard name must be a string and less than 100 characters"
        if not isinstance(keyboard["enabled"], bool):
            return False, "Enabled must be a boolean"
        if not isinstance(keyboard["connected"], bool):
            return False, "Connected must be a boolean"
        if not isinstance(keyboard["active"], bool):
            return False, "Active must be a boolean"
        if not isinstance(keyboard["layout"], str) or len(keyboard["layout"]) > 20:
            return False, "Layout must be a string and less than 20 characters"
        if not isinstance(keyboard["product"], str) or len(keyboard["product"]) > 100:
            return False, "Product must be a string and less than 100 characters"
        if not isinstance(keyboard["vendor"], str) or len(keyboard["vendor"]) > 100:
            return False, "Vendor must be a string and less than 100 characters"
        if not isinstance(keyboard["vid_pid"], list):
            return False, "VID/PID must be a list"
        if len(keyboard["vid_pid"]) > MAX_VID_PID_PER_KEYBOARD:
            return False, f"Number of VID/PID entries exceeds maximum allowed ({MAX_VID_PID_PER_KEYBOARD})"
        for vid_pid in keyboard["vid_pid"]:
            if not isinstance(vid_pid, str) or len(vid_pid) > 50:
                return False, "VID/PID entries must be strings and less than 50 characters"
            if not re.match(r'^VID_[0-9A-F]{4}&PID_[0-9A-F]{4}$', vid_pid, re.IGNORECASE):
                return False, "VID/PID entries must be in format VID_XXXX&PID_YYYY"
    
    return True, None

def create_backup():
    """Create a backup of the current config file."""
    if not os.path.exists(CONFIG_FILE):
        return
    
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"keyboard_config_{timestamp}.json")
    
    try:
        shutil.copy2(CONFIG_FILE, backup_file)
        # Keep only the last 5 backups
        backups = sorted([f for f in os.listdir(backup_dir) if f.startswith("keyboard_config_")])
        if len(backups) > 5:
            for old_backup in backups[:-5]:
                os.remove(os.path.join(backup_dir, old_backup))
    except Exception as e:
        print(f"[ERROR] Failed to create backup: {e}")

def save_config(config):
    """Save keyboard configuration to file with safety measures."""
    # Validate config
    is_valid, error_message = validate_config(config)
    if not is_valid:
        print(f"[ERROR] Invalid config: {error_message}")
        return False
    
    # Create backup before saving
    create_backup()
    
    # Save to temporary file first
    temp_file = f"{CONFIG_FILE}.tmp"
    try:
        with open(temp_file, 'w') as f:
            json.dump(config, f, indent=4)
        
        # Verify the temp file can be loaded
        with open(temp_file, 'r') as f:
            json.load(f)
        
        # If verification successful, replace the original file
        os.replace(temp_file, CONFIG_FILE)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save config: {e}")
        # Clean up temp file if it exists
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False

def extract_vid_pid(device_path):
    """Extracts the Vendor ID (VID) and Product ID (PID) from a device path string."""
    match = re.search(r'vid_([0-9A-Fa-f]{4})&pid_([0-9A-Fa-f]{4})', device_path, re.IGNORECASE)
    if match:
        return match.group(2).upper(), match.group(1).upper()  # PID, VID
    return None, None

def get_connected_keyboards():
    """Returns a list of device IDs for all connected keyboards."""
    pythoncom.CoInitialize()
    try:
        c = wmi.WMI()
        keyboards = [kb.deviceid for kb in c.Win32_Keyboard()]
        return keyboards
    finally:
        pythoncom.CoUninitialize()

def list_unique_devices_with_hwid():
    """Returns a sorted list of unique connected keyboards with their vendor, product, PID, VID, and HWID."""
    pythoncom.CoInitialize()
    try:
        keyboards = get_connected_keyboards()
        seen = set()
        result = []

        for device in hid.find_all_hid_devices():
            vendor = device.vendor_name or "Unknown Vendor"
            product = device.product_name or "Unknown Model"
            
            # Skip non-keyboard devices
            if "unknown" in product.lower() or "unknown" in vendor.lower():
                continue
                
            pid, vid = extract_vid_pid(device.device_path)
            if not (pid and vid):
                continue

            key = (vendor, product, pid, vid)
            if key in seen:
                continue
            seen.add(key)

            matching_hwid = next(
                (k for k in keyboards if f"VID_{vid}" in k and f"PID_{pid}" in k),
                None
            )

            if matching_hwid:
                result.append((vendor, product, pid, vid, matching_hwid))

        # Remove sorting to preserve order
        return result
    finally:
        pythoncom.CoUninitialize()

import re
import pythoncom

def parse_vid_pid(vid_pid_str):
    """Parses VID and PID from a string like 'VID_XXXX&PID_YYYY'."""
    match = re.search(r'VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})', vid_pid_str, re.IGNORECASE)
    if match:
        return match.group(2).upper(), match.group(1).upper()  # Return PID, VID
    return None

def is_keyboard_connected(keyboard, connected_vid_pid_set):
    """Check if any VID/PID of a keyboard is currently connected."""
    return any(
        (parsed := parse_vid_pid(vid_pid)) and parsed in connected_vid_pid_set
        for vid_pid in keyboard.get("vid_pid", [])
    )

def detect_active_keyboard():
    """Detects which configured keyboard is currently connected, based on VID & PID."""
    pythoncom.CoInitialize()
    try:
        connected = get_connected_keyboards()
        connected_vid_pid_set = {
            vid_pid for vid_pid in map(extract_vid_pid, connected) if vid_pid is not None
        }

        config = load_config()
        active_keyboard_name = None

        # Determine active keyboard
        for keyboard in config:
            if not keyboard.get("enabled", False):
                continue
            if is_keyboard_connected(keyboard, connected_vid_pid_set):
                active_keyboard_name = keyboard["name"]
                break

        # Update each keyboard's connection and active status
        for keyboard in config:
            connected = is_keyboard_connected(keyboard, connected_vid_pid_set)
            keyboard["connected"] = connected
            keyboard["active"] = connected and keyboard.get("enabled", False) and keyboard["name"] == active_keyboard_name

        return active_keyboard_name

    finally:
        pythoncom.CoUninitialize()

def get_current_input_language():
    """Returns the current Windows input language as a hex string."""
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    hkl = user32.GetKeyboardLayout(0)
    lang_id = hkl & 0xFFFF
    return f"{lang_id:08X}"

def force_input_language(layout_hex):
    """Forces the Windows input language to the specified layout."""
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    hkl = user32.LoadKeyboardLayoutW(layout_hex, KLF_ACTIVATE)
    if hkl == 0:
        print(f"[ERROR] Failed to switch to layout {layout_hex}.")
    else:
        user32.PostMessageW(HWND_BROADCAST, WM_INPUTLANGCHANGEREQUEST, 0, hkl)
        print(f"[ACTION] Language switched to {layout_hex}.")

def create_tray_icon():
    """Creates a system tray icon with menu."""
    def on_configure():
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        webbrowser.open('http://localhost:5000')

    def on_exit():
        icon.stop()
        os._exit(0)
    
    # Create a simple icon
    image = Image.new('RGB', (64, 64), color='white')
    dc = ImageDraw.Draw(image)
    dc.rectangle([16, 16, 48, 48], fill='black')
    
    menu = pystray.Menu(
        pystray.MenuItem('Open Web Interface', on_configure),
        pystray.MenuItem('Exit', on_exit)
    )
    
    icon = pystray.Icon("keyboard_switcher", image, "Keyboard Switcher", menu)
    return icon

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    config = load_config()
    print(f"[DEBUG] Loading config: {config}")
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
def update_config():
    # Check content length
    if request.content_length and request.content_length > MAX_CONFIG_SIZE:
        return jsonify({
            "status": "error",
            "message": f"Request payload too large. Maximum size is {MAX_CONFIG_SIZE/1024/1024}MB"
        }), 413

    config = request.json
    if config != load_config():
        print(f"[DEBUG] Updating config: {config}")
        if not save_config(config):
            return jsonify({"status": "error", "message": "Failed to save config"}), 500
    
    # Check if we need to update the layout
    active_keyboard = detect_active_keyboard()
    if active_keyboard:
        # Find the active keyboard in the config array
        active_keyboard_data = next((kb for kb in config if kb["name"] == active_keyboard), None)
        if active_keyboard_data:
            expected_layout = active_keyboard_data["layout"]
            current_layout = get_current_input_language()
            if current_layout != expected_layout:
                force_input_language(expected_layout)
    return jsonify({"status": "success"})

@app.route('/api/status', methods=['GET'])
def get_status():
    active_keyboard = detect_active_keyboard()
    current_layout = get_current_input_language()
    return jsonify({
        "active_keyboard": active_keyboard,
        "current_layout": current_layout
    })

@app.route('/api/detected_keyboards', methods=['GET'])
def get_detected_keyboards():
    """Returns both connected keyboards and ones from config file."""
    devices = list_unique_devices_with_hwid()
    config = load_config()
    
    # Create a set of connected device names for quick lookup
    connected_names = {f"{d[0]} {d[1]}" for d in devices}
    
    # Return all keyboards from config with their connection status
    result = []
    for keyboard in config:
        result.append({
            "vendor": keyboard["vendor"],
            "product": keyboard["product"],
            "vid_pid": keyboard["vid_pid"],
            "connected": keyboard["name"] in connected_names
        })
    
    # Add any newly connected keyboards not in config
    for vendor, product, pid, vid, _ in devices:
        name = f"{vendor} {product}"
        if name not in config:
            result.append({
                "vendor": vendor,
                "product": product,
                "vid_pid": [f"VID_{vid}&PID_{pid}"],
                "connected": True
            })
    
    return jsonify(result)

@app.route('/exit', methods=['POST'])
def close_backend():
    print("[INFO] Beacon received: shutting down...")
    shutdown_event.set()  # Signal the shutdown
    return '', 204

def run_flask():
    """Run the Flask application."""
    app.run(host='localhost', port=5000)

def main():
    """Main loop: detects active keyboard and switches input language if needed."""
    print("[INFO] Keyboard language switcher started.")
    last_keyboard = None
    
    # Create and start the system tray icon
    icon = create_tray_icon()
    icon.run_detached()
    
    while True:
        active_keyboard = detect_active_keyboard()
        if active_keyboard and active_keyboard != last_keyboard:
            config = load_config()
            # Find the active keyboard in the config array
            active_keyboard_data = next((kb for kb in config if kb["name"] == active_keyboard), None)
            if active_keyboard_data:
                expected_layout = active_keyboard_data["layout"]
                current_layout = get_current_input_language()
                print(f"[INFO] Active keyboard: {active_keyboard}")
                print(f"[INFO] Current layout: {current_layout} | Expected: {expected_layout}")
                if current_layout != expected_layout:
                    force_input_language(expected_layout)
            last_keyboard = active_keyboard
        sleep(1)

if __name__ == "__main__":
    main()

# pyinstaller --noconsole --onefile --hidden-import=wmi --hidden-import=pyautogui main.py
