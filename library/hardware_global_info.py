#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Asses_System_Info

This module gathers comprehensive system information including CPU, Memory, Disk, Network, 
and Environment details for Ansible. It now supports setting a custom log path via an Ansible argument.
"""

import os
import subprocess
import platform
import socket
import re
from ansible.module_utils.basic import AnsibleModule
import logging
import datetime

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
        logger.error(f"Command '{command}' failed with error: {e.stderr}")
        return dict(failed=True, msg=str(e.stderr))

def _set_speech(id=0, speaker_id=0, message=None, remediation_tasks=None):
    """Set up a speech structure with sentences, remediation tasks combined, and tags."""
    objects = []
    
    # Initial message
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

    # System analyzed message
    objects.append({ 
        "id": str(id), 
        "text": "System has been analyzed.", 
        "speaker_id": str(speaker_id), 
        "output_file": f"/tmp/inspection_report_{id}.wav",
        "tags": ["system", "status"]
    })
    id += 1

    return {
        "next_id": id,
        "objects": objects
    }

def _parse_cpu_info():
    """Parse /proc/cpuinfo to gather CPU information."""
    cpuinfo = {}
    with open('/proc/cpuinfo', 'r') as f:
        for line in f:
            if ':' in line:
                key, value = map(str.strip, line.split(':', 1))
                cpuinfo[key] = value
    return cpuinfo

def _define_limits():
    """Set up limits data structure."""
    logger.info("Defining system limits")
    return {
        'cpu_load': 80,  # Percentage
        'memory_usage': 90,  # Percentage
        'disk_usage': 85   # Percentage
    }

def assess_state():
    """Gather information about the system."""
    logger.info("Gathering system state")
    system_info = {
        'cpu': {'count': None, 'model': None, 'load': None},
        'disk': {'total': None, 'used': None, 'free': None, 'usage': None},
        'environment': {
            'python_version': platform.python_version(),
            'python_path': os.environ.get('PYTHONPATH', 'Not set'),
            'path': list(dict.fromkeys(os.environ.get('PATH', '').split(':'))),
            'ld_library_path': os.environ.get('LD_LIBRARY_PATH', 'Not set').split(':')
        },
        'limits': _define_limits(),
        'memory': {'total': None, 'used': None, 'available': None, 'usage': None},
        'network': {'hostname': socket.gethostname(), 'interfaces': {}},
        'system': {
            'os': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'architecture': platform.machine()
        }
    }

    # CPU Information
    cpuinfo = _parse_cpu_info()
    system_info['cpu']['count'] = int(cpuinfo.get('processor', 0)) + 1
    system_info['cpu']['model'] = cpuinfo.get('model name')

    # CPU Load
    load_output = _run_cmd("uptime", shell=True)
    if isinstance(load_output, str):
        load = re.search(r'load average: ([\d.]+)', load_output)
        if load:
            system_info['cpu']['load'] = float(load.group(1))

    # Memory Information
    meminfo = _run_cmd("cat /proc/meminfo", shell=True)
    if isinstance(meminfo, str):
        for line in meminfo.split('\n'):
            if line.startswith("MemTotal:"):
                system_info['memory']['total'] = int(line.split()[1]) * 1024
            elif line.startswith("MemAvailable:"):
                system_info['memory']['available'] = int(line.split()[1]) * 1024

    mem_used = _run_cmd("free -b | grep 'Mem:' | awk '{print $3}'", shell=True)
    if isinstance(mem_used, str):
        system_info['memory']['used'] = int(mem_used)
        system_info['memory']['usage'] = (system_info['memory']['used'] / system_info['memory']['total']) * 100 if system_info['memory']['total'] else 0

    # Disk Information
    disk_output = _run_cmd("df -B 1 /", shell=True)
    if isinstance(disk_output, str):
        for line in disk_output.split('\n'):
            if '/dev/' in line:
                parts = line.split()
                system_info['disk']['total'] = int(parts[1])
                system_info['disk']['used'] = int(parts[2])
                system_info['disk']['free'] = int(parts[3])
                system_info['disk']['usage'] = int(parts[4].rstrip('%'))

    # Network Information
    ip_output = _run_cmd("ip -o addr show", shell=True)
    if isinstance(ip_output, str):
        for iface in ip_output.split('\n'):
            if not iface.strip():
                continue
            parts = iface.split()
            interface = parts[1]
            if interface not in system_info['network']['interfaces']:
                system_info['network']['interfaces'][interface] = []
            addr_info = parts[-1].split('/')
            if len(addr_info) > 1:
                system_info['network']['interfaces'][interface].append({
                    'address': addr_info[0],
                    'netmask': addr_info[1] if len(addr_info) > 1 else None
                })

    return system_info

def define_remediation(info):
    """Define remediation tasks based on gathered information."""
    logger.info("Defining remediation tasks")
    remediation_tasks = []

    if info['cpu']['load'] > info['cpu']['count']:
        remediation_tasks.append({
            'action': 'investigate_high_load',
            'description': 'Investigate and resolve high system load',
            'reason': f'Current system load ({info["cpu"]["load"]}) exceeds CPU count ({info["cpu"]["count"]})',
            'tags': ['system', 'cpu']
        })

    if info['memory'].get('usage') and info['memory']['usage'] > 90:
        remediation_tasks.append({
            'action': 'free_memory',
            'description': 'Free up memory or add more RAM',
            'reason': f'Memory usage is high at {info["memory"]["usage"]}%',
            'tags': ['system', 'memory']
        })

    if info['disk'].get('usage') and info['disk']['usage'] > 85:
        remediation_tasks.append({
            'action': 'clear_disk_space',
            'description': 'Clear disk space or expand storage',
            'reason': f'Disk usage on / is high at {info["disk"]["usage"]}%',
            'tags': ['system', 'disk']
        })

    return remediation_tasks

def send_response(module, message, info, id_offset, remediation_tasks):
    """Generate a uniform response for the module with the given information."""
    logger.info("Sending response with facts")
    module.exit_json(
        changed=False,
        msg=message,
        ansible_facts={
            'actions': remediation_tasks,
            'data': {'host': info},
            'speech': _set_speech(id_offset, message=message, remediation_tasks=remediation_tasks),
        }
    )

def main():
    """Main function to run the Ansible module."""
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

    logger.info("Starting module execution")
    now = datetime.datetime.now()
    epoch = int(now.timestamp())
    message = f"Initiating System_Info gathering."

    info = assess_state()
    remediation_tasks = define_remediation(info)  # Get remediation tasks
    send_response(module, message, info, id_offset, remediation_tasks)  # Pass remediation tasks

if __name__ == '__main__':
    main()