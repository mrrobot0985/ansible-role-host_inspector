#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Detect_TPU_Coral

This module checks for the presence of Google Coral (both USB and PCIe versions), provides
information about the device along with remediation tasks if necessary. Now supports setting a custom log path via Ansible.
"""

import os
import subprocess
import re
from ansible.module_utils.basic import AnsibleModule
import logging
import datetime
import socket

def _setup_logging(log_path=None):
    """Configure logging based on whether a custom log path is provided."""
    if log_path:
        log_filename = log_path
        if not os.path.exists(os.path.dirname(log_path)):
            os.makedirs(os.path.dirname(log_path))
    else:
        logs_dir = 'logs'
        if not os.path.isdir(logs_dir):
            os.makedirs(logs_dir)
        now = datetime.datetime.now()
        epoch = int(now.timestamp())
        log_filename = f"{logs_dir}/{epoch}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()  # This will keep the console output
        ]
    )
    return logging.getLogger(__name__)

def _run_cmd(command, timeout=30, shell=True, check=False, text=True):
    """Run a shell command with error handling and timeout."""
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                shell=shell, timeout=timeout, check=check, text=text)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Command '{command}' timed out")
        return dict(failed=True, msg=f"Command '{command}' timed out")
    except subprocess.CalledProcessError as e:
        logger.info(f"No Google Coral Device found or command failed: {e.stderr}")
        return dict(failed=True, msg=f"Command '{command}' failed with error: {e.stderr}")

def _set_speech(id=0, speaker_id=0, message=None, tpu_present=False, remediation_tasks=None):
    """Set up a speech structure with sentences, combined remediation tasks, and tags."""
    objects = []
    if message:
        objects.append({ 
            "id": str(id), 
            "text": message, 
            "speaker_id": str(speaker_id), 
            "output_file": f"/tmp/inpection_report_{id}.wav", 
            "tags": ["initiation"]
        })
        id += 1

    # Combine all remediation tasks into one message with tags
    if remediation_tasks:
        actions_text = "Recommended actions are: "
        actions_tags = set()
        for task in remediation_tasks:
            actions_text += f"{task['description']} due to {task['reason']}. "
            actions_tags.update(task['tags'])
        
        objects.append({
            "id": str(id),
            "text": actions_text,
            "speaker_id": str(speaker_id),
            "output_file": f"/tmp/inpection_report_{id}.wav",
            "tags": list(actions_tags)
        })
        id += 1

    if tpu_present:
        speech_text = "Google Coral analysis completed. Coral device details gathered."
    else:
        speech_text = "Google Coral analysis completed. No Coral device found."
    objects.append({ 
        "id": str(id), 
        "text": speech_text, 
        "speaker_id": str(speaker_id), 
        "output_file": f"/tmp/inpection_report_{id}.wav",
        "tags": ["system", "tpu", "coral"]
    })
    id += 1

    return {
        "next_id": id,
        "objects": objects
    }

def check_google_coral():
    """Check for the presence of Google Coral (USB or PCIe) devices."""
    status = {
        'tpu_present': False,
        'tpus': [],
        'limits': define_limits(),
    }

    # Check for USB Coral TPU
    usb_devices = _run_cmd("lsusb | grep -i -E 'Google Inc. Edgetpu|Global Unichip Corp.'", shell=True)
    if isinstance(usb_devices, str):
        for line in usb_devices.splitlines():
            vendor_match = re.search(r'ID\s+(\w+:\w+)\s+(Google Inc. Edgetpu|Global Unichip Corp.)', line)
            if vendor_match:
                vendor, model = vendor_match.group(2), "Google Coral USB TPU"
                status['tpu_present'] = True
                status['tpus'].append({'vendor': vendor, 'model': model, 'type': 'USB'})

    # Check for PCIe Coral TPU
    pci_devices = _run_cmd("lspci | grep -i 'Google'", shell=True)
    if isinstance(pci_devices, str):
        for line in pci_devices.splitlines():
            if 'Google' in line:
                status['tpu_present'] = True
                status['tpus'].append({'vendor': 'Google', 'model': 'Coral PCIe TPU', 'type': 'PCIe'})

    return status

def assess_state():
    """Gather information about Google Coral devices."""
    logger.info("Assessing Google Coral state")
    return check_google_coral()

def define_limits():
    """Set up limits data structure. Currently, no limits are defined for Google Coral."""
    logger.info("Defining system limits")
    return {}

def define_remediation(info):
    """Define remediation tasks based on gathered Google Coral information."""
    remediation_tasks = []
    if info['tpu_present']:
        # Check if the TPU runtime is installed only if a TPU is present
        tpu_runtime = _run_cmd("dpkg -l | grep -i 'edgetpu-runtime'", shell=True)
        if isinstance(tpu_runtime, dict) or not tpu_runtime:
            remediation_tasks.append({
                'action': 'install_tpu_runtime',
                'description': 'Install Google Coral Edge TPU runtime',
                'reason': 'Edge TPU runtime not installed',
                'tags': ['system', 'tpu', 'coral']
            })
    return remediation_tasks

def send_response(module, message, info, id_offset):
    """Generate a uniform response for the module with the given information."""
    tpu_present = info['tpu_present']
    remediation_tasks = define_remediation(info)
    
    module.exit_json(
        changed=False,
        msg=message,
        ansible_facts={
            'actions': remediation_tasks,
            'data': {'host': {
                'tpu_coral': {
                    'tpu_present': tpu_present,
                    'tpus': info['tpus'],
                    'limits': info['limits']
                }
            }},
            'speech': _set_speech(id_offset, speaker_id=0, message=message, tpu_present=tpu_present, remediation_tasks=remediation_tasks),
        }
    )

def main():
    """Main function to run the Ansible module for Google Coral detection."""
    module = AnsibleModule(
        argument_spec=dict(
            id_offset=dict(default=0, type='int', required=False),
            log_path=dict(type='str', required=False)
        ),
        supports_check_mode=True,
    )

    id_offset = module.params['id_offset']
    log_path = module.params['log_path']

    global logger
    logger = _setup_logging(log_path)

    logger.info("Starting Google Coral module execution")
    now = datetime.datetime.now()
    epoch = int(now.timestamp())
    message = f"Checking for Google Coral devices."

    info = assess_state()

    send_response(module, message, info, id_offset)

if __name__ == '__main__':
    main()