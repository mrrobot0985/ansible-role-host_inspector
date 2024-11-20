#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Detect_GPU_Intel

This module checks for the presence of Intel GPUs or CPUs, verifies if Intel oneAPI is installed,
and gathers detailed GPU information. It provides remediation tasks only if Intel hardware is detected.
Now supports setting a custom log path via Ansible.
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
        logger.info(f"Command '{command}' returned an error: {e.stderr}")
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
        speech_text = "Intel hardware analysis completed."
    else:
        speech_text = "Intel hardware analysis completed. No Intel hardware found."
    objects.append({ 
        "id": str(id), 
        "text": speech_text, 
        "speaker_id": str(speaker_id), 
        "output_file": f"/tmp/inspection_report_{id}.wav",
        "tags": ["system", "gpu", "intel"]
    })
    id += 1

    return {
        "next_id": id,
        "objects": objects
    }

def check_intel_hardware():
    """Check for the presence of Intel GPU or CPU by PCI ID or CPU model."""
    status = {
        'gpu_present': False,
        'gpus': [],
        'intel_oneapi_installed': False,
        'intel_oneapi_version': None,
    }

    # Check for Intel CPU
    cpuinfo_output = _run_cmd("cat /proc/cpuinfo | grep -m 1 'model name'", shell=True)
    if isinstance(cpuinfo_output, str) and 'Intel' in cpuinfo_output:
        status['gpu_present'] = True
        cpu_model = cpuinfo_output.split(':')[1].strip()
        status['gpus'].append({'model': f"Integrated Graphics (CPU Model: {cpu_model})"})
    else:
        # Check for Intel GPU by PCI ID if CPU check fails
        pci_output = _run_cmd("lspci | grep -i 'VGA.*Intel'", shell=True)
        if isinstance(pci_output, str) and 'Intel' in pci_output:
            status['gpu_present'] = True
            for line in pci_output.strip().split('\n'):
                if 'Intel' in line:
                    # Extract PCI ID
                    pci_id = line.split()[0]
                    # Get detailed info
                    detail_output = _run_cmd(f"lspci -v -s {pci_id}", shell=True)
                    model = None
                    memory_size = None
                    for detail_line in detail_output.split('\n'):
                        if 'VGA compatible controller' in detail_line:
                            model = detail_line.split(':')[1].strip()
                        elif 'Memory at' in detail_line:
                            # Assuming the memory size follows 'Memory at ... [size=...]'
                            memory_match = re.search(r'size=(\d+)\w', detail_line)
                            if memory_match:
                                memory_size = memory_match.group(1)
                    
                    status['gpus'].append({
                        'model': model or "Unknown Intel GPU",
                        'memory_size': f"{memory_size}MB" if memory_size else "Unknown"
                    })

    # Check if Intel oneAPI is installed only if Intel hardware is detected
    if status['gpu_present']:
        oneapi_dir = "/opt/intel/oneapi"
        if os.path.exists(oneapi_dir):
            status['intel_oneapi_installed'] = True
            setvars_path = os.path.join(oneapi_dir, "setvars.sh")
            if os.path.isfile(setvars_path):
                with open(setvars_path, 'r') as file:
                    content = file.read()
                    version_match = re.search(r'# Version: (\d+\.\d+\.\d+\.\d+)', content)
                    if version_match:
                        status['intel_oneapi_version'] = version_match.group(1)

    # Attempt to get more accurate model name using glxinfo only if Intel hardware is present
    if status['gpus']:
        glxinfo_output = _run_cmd("glxinfo | grep -i 'OpenGL renderer'", shell=True)
        if isinstance(glxinfo_output, str):
            for gpu in status['gpus']:
                if 'model' in gpu and 'Unknown Intel' in gpu['model']:
                    gpu['model'] = glxinfo_output.split(':', 1)[1].strip().replace('Mesa DRI', '').strip()

    return status

def assess_state():
    """Gather information about Intel hardware."""
    logger.info("Assessing Intel hardware state")
    return check_intel_hardware()

def define_remediation(info):
    """Define remediation tasks based on gathered Intel hardware information."""
    remediation_tasks = []
    # Only add remediation tasks if Intel hardware is detected
    if info['gpu_present']:
        if not info['intel_oneapi_installed']:
            remediation_tasks.append({
                'action': 'install_intel_oneapi',
                'description': 'Install Intel oneAPI toolkit',
                'reason': 'Intel oneAPI not found',
                'tags': ['system', 'gpu', 'intel']
            })
    return remediation_tasks

def define_limits():
    """Set up limits data structure. Currently, no limits are defined for Intel hardware."""
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
                'gpu_intel': {
                    'gpu_present': gpu_present,
                    'gpus': info['gpus'],
                    'limits': define_limits(),
                    'oneapi_installed': info['intel_oneapi_installed'],
                    'oneapi_version': info['intel_oneapi_version']
                }
            }},
            'speech': _set_speech(id_offset, speaker_id=0, message=message, gpu_present=gpu_present, remediation_tasks=remediation_tasks),
        }
    )

def main():
    """Main function to run the Ansible module for Intel hardware detection."""
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

    logger.info("Starting Intel hardware module execution")
    now = datetime.datetime.now()
    epoch = int(now.timestamp())
    message = f"Checking for Intel GPUs."

    info = assess_state()

    send_response(module, message, info, id_offset)

if __name__ == '__main__':
    main()