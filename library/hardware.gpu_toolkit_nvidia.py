#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Detect_Toolkit_Nvidia

This module checks for the presence and configuration of various NVIDIA toolkits,
including CUDA Toolkit, NVIDIA Container Toolkit, and other NVIDIA tools.
It provides detailed information and remediation tasks if necessary. Now supports setting a custom log path via Ansible.
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
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                shell=shell, timeout=timeout, check=check, text=text)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Command '{command}' timed out")
        return dict(failed=True, msg=f"Command '{command}' timed out")
    except subprocess.CalledProcessError as e:
        logger.info(f"No NVIDIA Toolkit found or command failed: {e.stderr.strip()}")
        return dict(failed=True, msg=f"Command '{command}' failed with error: {e.stderr.strip()}")
    
def _set_speech(id=0, speaker_id=0, message=None, gpu_present=False, remediation_tasks=None):
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
            actions_text += f"{task['action']} due to {task['reason']}. "
            actions_tags.update(task['tags'])
        
        objects.append({
            "id": str(id),
            "text": actions_text,
            "speaker_id": str(speaker_id),
            "output_file": f"/tmp/inpection_report_{id}.wav",
            "tags": list(actions_tags)
        })
        id += 1

    if gpu_present:
        speech_text = "NVIDIA Toolkit analysis completed."
    else:
        speech_text = "NVIDIA Toolkit analysis completed. No NVIDIA GPU found."
    objects.append({ 
        "id": str(id), 
        "text": speech_text, 
        "speaker_id": str(speaker_id), 
        "output_file": f"/tmp/inpection_report_{id}.wav",
        "tags": ["system", "gpu", "nvidia"]
    })
    id += 1

    return {
        "next_id": id,
        "objects": objects
    }

def check_nvidia_toolkit():
    toolkit_info = {
        'cuda_toolkit': {
            'version': None,
            'path': None
        },
        'container_toolkit': {
            'drivers_installed': [],
            'installed': False,
            'version': None,
            'docker_configured': False,
            'nvidia_ctk_available': False,
            'cdi_specification_exists': False
        },
        'nvidia_nsight': {
            'installed': False
        }
    }

    # Check for NVIDIA Drivers for multiple GPUs
    nvidia_smi_output = _run_cmd("nvidia-smi --query-gpu=index,driver_version --format=csv,noheader,nounits", shell=True)
    if isinstance(nvidia_smi_output, str):
        for line in nvidia_smi_output.split('\n'):
            if line.strip():
                index, version = line.split(',')
                toolkit_info['container_toolkit']['drivers_installed'].append({
                    'index': index,
                    'driver_version': version.strip()
                })

    # Only check for CUDA Toolkit if NVIDIA drivers are installed
    if toolkit_info['container_toolkit']['drivers_installed']:
        nvcc_output = _run_cmd("nvcc --version", shell=True)
        if isinstance(nvcc_output, str):
            version_match = re.search(r'release (\d+\.\d+).', nvcc_output)
            if version_match:
                toolkit_info['cuda_toolkit']['version'] = version_match.group(1)
            cuda_home = os.environ.get('CUDA_HOME')
            toolkit_info['cuda_toolkit']['path'] = cuda_home if cuda_home else 'Not set'

    # Check for NVIDIA Container Toolkit
    nvidia_ctk_output = _run_cmd("nvidia-ctk --version", shell=True)
    if isinstance(nvidia_ctk_output, str):
        toolkit_info['container_toolkit']['installed'] = True
        version_match = re.search(r'version (\d+\.\d+\.\d+)', nvidia_ctk_output)
        if version_match:
            toolkit_info['container_toolkit']['version'] = version_match.group(1)
        toolkit_info['container_toolkit']['nvidia_ctk_available'] = True

    # Check for Docker Configuration for NVIDIA
    docker_config_path = '/etc/docker/daemon.json'
    if os.path.exists(docker_config_path):
        with open(docker_config_path, 'r') as config_file:
            config_content = config_file.read()
            toolkit_info['container_toolkit']['docker_configured'] = '"nvidia"' in config_content

    # Check for CDI Specification
    cdi_spec_path = '/etc/cdi/nvidia.yaml'
    toolkit_info['container_toolkit']['cdi_specification_exists'] = os.path.exists(cdi_spec_path)

    # Check for NVIDIA Nsight
    nsight_output = _run_cmd("nvidia-nsight --version", shell=True)
    if isinstance(nsight_output, str):
        toolkit_info['nvidia_nsight']['installed'] = True

    return toolkit_info

def assess_state():
    """Gather information about NVIDIA toolkits."""
    logger.info("Assessing NVIDIA toolkits state")
    return check_nvidia_toolkit()

def define_remediation(info):
    """Define remediation tasks based on gathered NVIDIA toolkits information."""
    remediation_tasks = []
    cuda_toolkit = info.get('cuda_toolkit', {})
    container_toolkit = info.get('container_toolkit', {})
    
    # Only suggest remediation if NVIDIA hardware or toolkits are detected
    if container_toolkit.get('drivers_installed') or container_toolkit['installed']:
        if not cuda_toolkit.get('version'):
            remediation_tasks.append({
                'action': 'install_cuda',
                'description': 'Install CUDA Toolkit',
                'reason': 'CUDA Toolkit not installed or not found in PATH',
                'tags': ['system', 'gpu', 'nvidia']
            })

        if not container_toolkit.get('installed'):
            remediation_tasks.append({
                'action': 'install_container_toolkit',
                'description': 'Install NVIDIA Container Toolkit',
                'reason': 'NVIDIA Container Toolkit not installed or nvidia-ctk not available',
                'tags': ['system', 'gpu', 'nvidia', 'containers']
            })

        if not container_toolkit.get('docker_configured') and container_toolkit['installed']:
            remediation_tasks.append({
                'action': 'configure_docker',
                'description': 'Configure Docker to use NVIDIA runtime',
                'reason': 'Docker not configured to use NVIDIA runtime',
                'tags': ['system', 'gpu', 'nvidia', 'containers']
            })

        if not container_toolkit.get('cdi_specification_exists') and container_toolkit['installed']:
            remediation_tasks.append({
                'action': 'generate_cdi_spec',
                'description': 'Generate CDI specification for NVIDIA devices',
                'reason': 'CDI specification for NVIDIA not found',
                'tags': ['system', 'gpu', 'nvidia', 'toolkit']
            })

        if not info.get('nvidia_nsight', {}).get('installed'):
            remediation_tasks.append({
                'action': 'install_nsight',
                'description': 'Install NVIDIA Nsight',
                'reason': 'NVIDIA Nsight not installed',
                'tags': ['system', 'gpu', 'nvidia', 'toolkit']
            })

    return remediation_tasks

def send_response(module, message, info, id_offset):
    """Generate a uniform response for the module with the given information."""
    gpu_present = len(info['container_toolkit']['drivers_installed']) > 0
    remediation_tasks = define_remediation(info)
    
    module.exit_json(
        changed=False,
        msg=message,
        ansible_facts={
            'actions': remediation_tasks,
            'data': {'host': {
                'gpu_nvidia': {
                    'toolkit': info
                }
            }},
            'speech': _set_speech(id_offset, speaker_id=0, message=message, gpu_present=gpu_present, remediation_tasks=remediation_tasks),
        }
    )

def main():
    """Main function to run the Ansible module for NVIDIA toolkit detection."""
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

    logger.info("Starting NVIDIA toolkits module execution")
    now = datetime.datetime.now()
    epoch = int(now.timestamp())
    message = f"Checking for NVIDIA Toolkits."

    info = assess_state()

    send_response(module, message, info, id_offset)

if __name__ == '__main__':
    main()