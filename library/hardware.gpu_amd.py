#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Detect_GPU_AMD

This module checks for the presence of AMD GPUs, gathers information about them,
and provides remediation tasks if an AMD GPU is detected but has issues. 
It now allows setting a custom log path via Ansible.
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
        logger.info("No AMD GPU found or command failed")
        return dict(failed=True, msg=str(e.stderr))

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
            actions_text += f"{task['action']} due to {task['reason']}. "
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
        objects.append({ 
            "id": str(id), 
            "text": "AMD GPU analysis completed.", 
            "speaker_id": str(speaker_id), 
            "output_file": f"/tmp/inspection_report_{id}.wav",
            "tags": ["system", "gpu", "amd"]
        })
    else:
        objects.append({ 
            "id": str(id), 
            "text": "AMD GPU analysis completed. No AMD GPU found.", 
            "speaker_id": str(speaker_id), 
            "output_file": f"/tmp/inspection_report_{id}.wav",
            "tags": ["system", "gpu", "amd"]
        })
    id += 1

    return {
        "next_id": id,
        "objects": objects
    }

def check_amd_gpu():
    """Check for the presence of AMD GPUs and gather information."""
    status = {
        'gpu_present': False,
        'gpus': [],
        'remediation_tasks': []
    }

    lspci_output = _run_cmd("lspci | grep -i 'VGA.*AMD'", shell=True)
    if isinstance(lspci_output, str):
        status['gpu_present'] = True
        for line in lspci_output.splitlines():
            gpu_info = re.search(r'(.*)\s\[AMD/ATI\](.*)', line)
            if gpu_info:
                model = gpu_info.group(2).strip()
                status['gpus'].append({'model': model})

        # Check for AMDGPU drivers
        amdgpu_driver = _run_cmd("modinfo amdgpu", shell=True)
        if isinstance(amdgpu_driver, dict) or not amdgpu_driver:
            status['remediation_tasks'].append({
                'action': 'install_amd_gpu_drivers',
                'description': 'Install AMD GPU drivers',
                'reason': 'AMD GPU drivers not detected',
                'tags': ['system', 'gpu', 'amd']
            })

        # Check for ROCm installation
        rocm_version = _run_cmd("rocminfo | grep -i 'ROCm Version'", shell=True)
        if isinstance(rocm_version, dict) or not rocm_version:
            status['remediation_tasks'].append({
                'action': 'install_rocm',
                'description': 'Install ROCm for GPGPU computing',
                'reason': 'ROCm not installed or not found',
                'tags': ['system', 'gpu', 'amd']
            })
    
    return status

def assess_state():
    """Gather information about AMD GPUs."""
    logger.info("Assessing AMD GPU state")
    return check_amd_gpu()

def define_limits():
    """Set up limits data structure. Currently, no limits are defined for AMD GPUs."""
    logger.info("Defining system limits for AMD GPUs")
    return {}

def define_remediation(info):
    """Define remediation tasks based on gathered AMD GPU information."""
    logger.info("Defining remediation tasks for AMD GPUs")
    return info.get('remediation_tasks', [])

def send_response(module, message, info, id_offset):
    """Generate a uniform response for the module with the given information."""
    gpu_present = info.get('gpu_present', False)
    remediation_tasks = define_remediation(info)
    
    module.exit_json(
        changed=False,
        msg=message,
        ansible_facts={
            'actions': remediation_tasks,
            'data': {'host': {
                'gpu_amd': {
                    'gpu_present': gpu_present,
                    'gpus': info['gpus'],
                    'limits': define_limits(),
                }
            }},
            'speech': _set_speech(id_offset, speaker_id=0, message=message, gpu_present=gpu_present, remediation_tasks=remediation_tasks),
        }
    )

def main():
    """Main function to run the Ansible module for AMD GPU detection."""
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

    logger.info("Starting AMD GPU module execution")
    now = datetime.datetime.now()
    epoch = int(now.timestamp())
    message = f"Checking for AMD GPUs."

    info = assess_state()

    send_response(module, message, info, id_offset)

if __name__ == '__main__':
    main()