#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Detect_GPU_Nvidia

This module checks for the presence of NVIDIA GPUs, gathers detailed information about them,
and provides remediation tasks if issues are detected. It now allows setting a custom log path via Ansible.
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

def _run_cmd(command, timeout=30, shell=True, check=True, text=True):
    """Run a shell command with error handling and timeout."""
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                shell=shell, timeout=timeout, check=check, text=text)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Command '{command}' timed out")
        return dict(failed=True, msg=f"Command '{command}' timed out")
    except subprocess.CalledProcessError as e:
        logger.info(f"No NVIDIA GPU found or command failed: {e.stderr}")
        return dict(failed=True, msg=f"Command '{command}' failed with error: {e.stderr}")

def _set_speech(id=0, speaker_id=0, message=None, gpu_present=False, remediation_tasks=None):
    """Set up a speech structure with sentences, combined remediation tasks, and tags."""
    objects = []
    
    if message:
        objects.append({ 
            "id": str(id), 
            "text": message, 
            "speaker_id": str(speaker_id), 
            "output_file": f"/tmp/inspection_report_{id}.wav", 
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
            "output_file": f"/tmp/inspection_report_{id}.wav",
            "tags": list(actions_tags)
        })
        id += 1

    if gpu_present:
        speech_text = "NVIDIA GPU analysis completed. Detailed"
    else:
        speech_text = "NVIDIA GPU analysis completed. No NVIDIA GPU found."
    objects.append({ 
        "id": str(id), 
        "text": speech_text, 
        "speaker_id": str(speaker_id), 
        "output_file": f"/tmp/inspection_report_{id}.wav",
        "tags": ["system", "gpu", "nvidia"]
    })
    id += 1

    return {
        "next_id": id,
        "objects": objects
    }

def check_nvidia_gpu():
    gpu_info = {
        'gpu_present': False,
        'gpus': []
    }

    # Check for NVIDIA GPUs using nvidia-smi for detailed info
    nvidia_smi_output = _run_cmd("nvidia-smi --query-gpu=index,gpu_uuid,gpu_name,memory.total,power.max_limit,clocks.max.graphics,clocks.max.sm,clocks.max.memory,driver_version,pci.bus_id --format=csv,noheader")
    
    if isinstance(nvidia_smi_output, str):
        for line in nvidia_smi_output.split('\n'):
            if line:
                vals = [val.strip() for val in line.split(',')]
                gpu_dict = {
                    'driver_version': vals[8],
                    'index': vals[0],
                    'model': vals[2],
                    'pci_id': vals[9],
                    'stats': {
                        'clock_max_graphics': vals[5],
                        'clock_max_memory': vals[7],
                        'clock_max_sm': vals[6],
                        'memory_total': vals[3],
                        'power_cur_limit': None,
                        'power_max_limit': vals[4],
                        },
                    'uuid': vals[1],
                }
                gpu_info['gpus'].append(gpu_dict)
                gpu_info['gpu_present'] = True

        # Now, query for power details
        for gpu in gpu_info['gpus']:
            power_details = _run_cmd(f"nvidia-smi -q -d POWER -i {gpu['index']}")
            if isinstance(power_details, str):
                match = re.search(r'Current Power Limit\s*:\s*([\d.]+)\s*W', power_details)
                if match:
                    gpu['stats']['power_cur_limit'] = match.group(1) + ' W'
    
    else:
        # If nvidia-smi fails, fallback to lspci
        lspci_output = _run_cmd("lspci | grep -i nvidia")
        if isinstance(lspci_output, str) and "NVIDIA" in lspci_output:
            gpu_info['gpu_present'] = True
            gpu_info['gpus'].append({'model': 'Unknown', 'uuid': 'Unknown', 'pci_id': None})

    return gpu_info

def assess_state():
    """Gather information about NVIDIA GPUs."""
    logger.info("Assessing NVIDIA GPU state")
    return check_nvidia_gpu()

def define_remediation(info):
    """Define remediation tasks based on gathered NVIDIA GPU information."""
    remediation_tasks = []
    
    if info['gpu_present']:
        for i, gpu in enumerate(info['gpus']):
            if 'driver_version' not in gpu or not gpu['driver_version'].strip():
                remediation_tasks.append({
                    'action': 'install_nvidia_driver',
                    'description': 'Install or update NVIDIA GPU drivers',
                    'reason': f'GPU {i} driver version not detected or outdated',
                    'tags': ['system', 'gpu', 'nvidia']
                })
            # Additional checks could be added here, like performance tuning based on the detailed info

    return remediation_tasks

def define_limits():
    """Set up limits data structure. Currently, no limits are defined."""
    logger.info("Defining system limits")
    return {}

def send_response(module, message, info, id_offset):
    """Generate a uniform response for the module with the given information."""
    gpu_present = info['gpu_present']
    remediation_tasks = define_remediation(info)
    
    module.exit_json(
        changed=False,
        msg=message,
        ansible_facts={
            'actions': remediation_tasks,
            'data': {'host': {
                'gpu_nvidia': {
                    'gpu_present': gpu_present,
                    'gpus': info['gpus'],
                    'limits': define_limits()
                }
            }},
            'speech': _set_speech(id_offset, speaker_id=0, message=message, gpu_present=gpu_present, remediation_tasks=remediation_tasks),
        }
    )

def main():
    """Main function to run the Ansible module for NVIDIA GPU detection."""
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

    logger.info("Starting NVIDIA GPU module execution")
    now = datetime.datetime.now()
    epoch = int(now.timestamp())
    message = f"Checking for NVIDIA GPUs."

    info = assess_state()

    send_response(module, message, info, id_offset)

if __name__ == '__main__':
    main()