"""
===============================================================================
MikroTik Automated Multi-Threaded Config Backup
===============================================================================

Author: Network Engineer
Purpose:
    Automates mass configuration backups (/export) across multiple MikroTik 
    devices in parallel.

How It Works:
    1. Directory Management:
       Automatically creates a dated backup folder (e.g., '25_sep_2026') 
       in the script directory.

    2. Device Inventory:
       Loads grouped switch credentials and connection details from 'devices.yaml'.

    3. Concurrent Export:
       - Uses ThreadPoolExecutor to back up switches simultaneously via Netmiko.
       - Appends '+ct400w' to the username to strip MikroTik terminal escape codes 
         and color formatting, ensuring clean, plain-text .rsc files.
       - Queries '/system identity' to dynamically name each file after the device.

Output:
    Saves individual '<hostname>.rsc' configuration files into the dated folder.
===============================================================================
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import copy
import yaml
from netmiko import ConnectHandler


# make backup folder

now = datetime.now()
folder_name = now.strftime("%d_%b_%Y").lower()

backup_dir = Path(__file__).resolve().parent / folder_name
backup_dir.mkdir(parents=True, exist_ok=True)


# backup single switch

def export_config(switch_data):

    switch = copy.deepcopy(switch_data)
    host = switch.get('host', 'unknown')

    print('Connecting to:', host)

    # disable mikrotik colors/terminal formatting
    username = switch.get('username', '')
    if username and not any(username.endswith(sfx) for sfx in ['+ct', '+t', '+c']):
        switch['username'] = f"{username}+ct400w"

    switch.setdefault('conn_timeout', 60)

    try:
        connection = ConnectHandler(**switch)

        # get hostname
        identity_raw = connection.send_command('/system identity print', read_timeout=30)
        hostname = identity_raw.split()[-1]

        # export configuration
        config_text = connection.send_command('/export', read_timeout=120)
        connection.disconnect()

        # save file
        filepath = backup_dir / f"{hostname}.rsc"

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(config_text)

        print(f"DONE: {hostname} ({host}) -> {filepath.name}")
        return f"OK: {hostname}"

    except Exception as error:
        print(f"ERROR: {host} -> {error}")
        return f"ERROR: {host}"


# load devices

with open('devices.yaml', 'r', encoding='utf-8') as file:
    devices_data = yaml.safe_load(file)
    groups = devices_data.get('groups', {})


# make device list

all_switches = []

for group in groups:
    for switch in groups[group]:
        all_switches.append(switch)

print(f"Total devices found: {len(all_switches)}")
print()


# multi run

with ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(export_config, switch) for switch in all_switches]

    for future in as_completed(futures):
        result = future.result()
