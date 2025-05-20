import pywinusb.hid as hid
import tkinter as tk
import wmi
import re

def extract_vid_pid(device_path):
    """
    Extracts the Vendor ID (VID) and Product ID (PID) from a device path string.
    Returns (pid, vid) as uppercase strings, or (None, None) if not found.
    """
    match = re.search(r'vid_([0-9A-Fa-f]{4})&pid_([0-9A-Fa-f]{4})', device_path, re.IGNORECASE)
    if match:
        return match.group(2).upper(), match.group(1).upper()  # PID, VID
    return None, None

def get_connected_keyboards():
    """
    Returns a list of device IDs for all connected keyboards (uppercase).
    """
    c = wmi.WMI()
    return [kb.deviceid.upper() for kb in c.Win32_Keyboard()]

def list_unique_devices_with_hwid():
    """
    Returns a sorted list of unique connected keyboards with their vendor, product, PID, VID, and HWID.
    """
    keyboards = get_connected_keyboards()
    seen = set()
    result = []

    for device in hid.find_all_hid_devices():
        vendor = device.vendor_name or "Unknown Vendor"
        product = device.product_name or "Unknown Model"
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

    result.sort(key=lambda x: (x[0].lower(), x[1].lower()))
    return result

def copy_to_clipboard(vid, pid, button):
    """
    Copies the HWID (VID & PID) to the clipboard and provides user feedback in the GUI.
    """
    root.clipboard_clear()
    root.clipboard_append(f"VID_{vid}&PID_{pid}")
    original_text = button["text"]
    button.config(text="✔️ Copied", state="disabled")
    button.after(1500, lambda: button.config(text=original_text, state="normal"))

def build_gui(device_list):
    """
    Builds and runs the Tkinter GUI to display detected keyboards and allow copying their HWIDs.
    """
    global root
    root = tk.Tk()
    root.title("Detected Keyboards")
    root.geometry("820x400")
    root.configure(bg="#f0f0f0")

    # Header frame
    header_frame = tk.Frame(root, bg="#4a4a4a", padx=20, pady=10)
    header_frame.pack(fill="x")
    title = tk.Label(header_frame, text="Keyboards with detected HWID:", font=("Helvetica", 16, "bold"), bg="#4a4a4a", fg="white")
    title.pack()

    # Main content frame
    content_frame = tk.Frame(root, bg="#f0f0f0", padx=20, pady=10)
    content_frame.pack(fill="both", expand=True)

    for vendor, product, pid, vid, hwid in device_list:
        frame = tk.Frame(content_frame, bg="#ffffff", bd=1, relief="solid", padx=15, pady=10)
        frame.pack(fill="x", pady=5)

        label_text = f"{vendor} → {product} : VID_{vid} | PID_{pid}"
        label = tk.Label(frame, text=label_text, font=("Courier", 11), bg="#ffffff", anchor="w")
        label.pack(side="left", fill="x", expand=True)

        btn = tk.Button(frame, text="Copy HWID", width=12, font=("Helvetica", 10), bg="#4a4a4a", fg="white", relief="flat", padx=10, pady=5)
        btn.pack(side="right", padx=5)
        btn.configure(command=lambda vid=vid, pid=pid, b=btn: copy_to_clipboard(vid, pid, b))

    root.mainloop()

if __name__ == "__main__":
    devices = list_unique_devices_with_hwid()
    if not devices:
        print("No keyboards with HWID detected.")
    else:
        build_gui(devices)
