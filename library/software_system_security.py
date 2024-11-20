#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ansible.module_utils.basic import AnsibleModule
import subprocess
import re
import os
import platform
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
        logger.error(f"Command '{command}' failed with error: {e.stderr}")
        return dict(failed=True, msg=str(e.stderr))

def _set_speech(id=0, speaker_id=0, message=None, remediation_tasks=None):
    """Set up a speech structure with sentences, combined remediation tasks, and tags."""
    objects = []
    if message:
        objects.append({ 
            "id": str(id), 
            "text": message, 
            "speaker_id": str(speaker_id), 
            "output_file": f"/tmp/security_report_{id}.wav", 
            "tags": ["initiation", "security"]
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
            "output_file": f"/tmp/security_report_{id}.wav",
            "tags": list(actions_tags)
        })
        id += 1

    objects.append({ 
        "id": str(id), 
        "text": "Security analysis completed.", 
        "speaker_id": str(speaker_id), 
        "output_file": f"/tmp/security_report_{id}.wav",
        "tags": ["system", "security", "status"]
    })
    id += 1

    return {
        "next_id": id,
        "objects": objects
    }

def _parse_apt_output(output):
    result = {
        "upgraded": 0,
        "newly_installed": 0,
        "to_remove": 0,
        "not_upgraded": 0,
        "upgradable_packages": [],
        "upgradable_packages_deferred": []
    }

    lines = output.split('\n')
    for idx, line in enumerate(lines):
        if "upgraded," in line:
            try:
                parts = line.split(',')
                if len(parts) >= 4:
                    result["upgraded"] = int(parts[0].split()[0])
                    result["newly_installed"] = int(parts[1].split()[0])
                    result["to_remove"] = int(parts[2].split()[0])
                    result["not_upgraded"] = int(parts[3].split()[0])
            except (ValueError, IndexError):
                logger.error(f"Failed to parse apt-get output line: {line}")
        elif "deferred due to phasing:" in line:
            try:
                next_line_index = idx + 1
                if next_line_index < len(lines):
                    packages = lines[next_line_index].strip()
                    if packages:
                        result["upgradable_packages_deferred"] = packages.split()
            except IndexError:
                logger.error(f"Could not find packages deferred due to phasing below line: {line}")

        elif line.startswith("Inst"):
            try:
                package = line.split()[1]
                if package not in result["upgradable_packages_deferred"]:  # Avoid duplicates
                    result["upgradable_packages"].append(package)
            except IndexError:
                logger.error(f"Failed to parse package from Inst line: {line}")

    # Set updates_available to True if there are upgradable packages not deferred
    result['updates_available'] = len(result['upgradable_packages']) > 0

    return result

def assess_state():
    """Gather security information about the system across different OS."""
    logger.info("Assessing security state for multiple OS")
    security_info = {
        "firewall_status": check_firewall_status(),
        "limits": _define_limits(),
        "patches": check_patches(),
        "ssh_config": check_ssh_config(),
    }
    return security_info

def _define_limits():
    """Set up limits data structure for security checks."""
    logger.info("Defining security limits")
    return {
        'updates_available': False,
        'firewall_active': True
    }

def check_ssh_config():
    """Check and return the SSH configuration."""
    ssh_config = {}
    sshd_config_paths = ['/etc/ssh/sshd_config', '/etc/sshd_config']
    for path in sshd_config_paths:
        if os.path.exists(path):
            with open(path, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        try:
                            key, value = line.split(None, 1)
                            ssh_config[key.strip()] = value.strip()
                        except ValueError:
                            pass
            break
    else:
        ssh_config = {"error": "sshd_config not found"}
    return ssh_config

def check_firewall_status():
    """Check the status of various firewalls on different OS."""
    firewall_status = {}
    system = platform.system().lower()

    if system == "linux":
        try:
            subprocess.run(['iptables', '-L', '-t', 'filter'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            try:
                result = subprocess.run(['sudo', '-n', 'iptables', '-L', '-t', 'filter'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    firewall_status["iptables"] = "active"
                    output = result.stdout
                    firewall_status["iptables_rules"] = "configured" if "ACCEPT" in output or "DROP" in output else "empty"
                else:
                    firewall_status["iptables"] = "error"
                    logger.error(f"iptables command with sudo failed with return code {result.returncode}")
            except subprocess.CalledProcessError as e:
                firewall_status["iptables"] = "not available"
                logger.error(f"iptables command failed with error: {e.stderr}")
        except FileNotFoundError:
            firewall_status["iptables"] = "not available"
            firewall_status["iptables_rules"] = "not available"

        if os.path.exists('/usr/sbin/ufw'):
            try:
                ufw_status = _run_cmd(['sudo', 'ufw', 'status', 'verbose'], shell=False)
                if isinstance(ufw_status, dict) and ufw_status.get('failed'):
                    firewall_status["ufw"] = "error"
                    logger.error(f"UFW status check failed: {ufw_status.get('msg', 'No specific error message')}")
                else:
                    firewall_status["ufw"] = "active" if "Status: active" in ufw_status else "inactive"
            except subprocess.CalledProcessError:
                firewall_status["ufw"] = "error"
                logger.error("Failed to check UFW status")
        else:
            firewall_status["ufw"] = "not installed"

    elif system == "windows":
        try:
            firewall_status["windows_firewall"] = "active" if subprocess.run(['netsh', 'advfirewall', 'show', 'allprofiles', 'state'], 
                                                                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0 else "inactive"
        except FileNotFoundError:
            firewall_status["windows_firewall"] = "not available"

    elif system == "darwin":  
        try:
            output = _run_cmd(['pfctl', '-s', 'info'])
            firewall_status["pf"] = "active" if "Status: Enabled" in output else "inactive"
        except (subprocess.CalledProcessError, FileNotFoundError):
            firewall_status["pf"] = "not available"

    return firewall_status

def check_patches():
    """Check for available system updates/patches across different OS."""
    patches = {}
    system = platform.system().lower()

    if system == "linux":
        if os.path.exists('/usr/bin/yum'):
            try:
                output = _run_cmd(['yum', 'check-update'])
                patches['updates_available'] = "updates_available" in output
                patches['yum_output'] = output
            except subprocess.CalledProcessError:
                patches['error'] = "Failed to run yum check-update"
        elif os.path.exists('/usr/bin/apt-get'):
            try:
                result = subprocess.run(['sudo', 'apt-get', 'upgrade', '-s'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                output = result.stdout
                patches['updates_available'] = "The following packages have been kept back" in output or "Inst" in output or "not upgraded" in output or result.returncode != 0
                parsed_info = _parse_apt_output(output)
                patches.update(parsed_info)
            except subprocess.CalledProcessError as e:
                patches['apt_output'] = f"Error executing apt-get upgrade -s: {e.stdout + e.stderr}"
                patches['updates_available'] = False
                logger.error(f"apt-get upgrade -s failed: {e}")
            except Exception as e:
                patches['apt_output'] = f"Unexpected error: {str(e)}"
                patches['updates_available'] = False
                logger.error(f"Unexpected error during apt-get upgrade check: {e}")
        elif os.path.exists('/usr/bin/pacman'):
            try:
                output = _run_cmd(['pacman', '-Qu'])
                patches['updates_available'] = bool(output)
                patches['pacman_output'] = output
            except subprocess.CalledProcessError:
                patches['error'] = "Failed to run pacman -Qu"
        elif os.path.exists('/usr/bin/zypper'):
            try:
                output = _run_cmd(['zypper', 'list-updates'])
                patches['updates_available'] = "No updates found" not in output
                patches['zypper_output'] = output
            except subprocess.CalledProcessError:
                patches['error'] = "Failed to run zypper list-updates"
    elif system == "windows":
        try:
            output = _run_cmd(['powershell', '-Command', 'Get-WindowsUpdate'])
            patches['updates_available'] = "No updates found" not in output
            patches['windows_output'] = output
        except subprocess.CalledProcessError:
            patches['error'] = "Failed to check Windows updates"
    elif system == "darwin":
        try:
            output = _run_cmd(['softwareupdate', '-l'])
            patches['updates_available'] = "No new software available" not in output
            patches['softwareupdate_output'] = output
        except subprocess.CalledProcessError:
            patches['error'] = "Failed to check macOS updates"

    return patches

def define_remediation(info):
    """Define remediation tasks based on security information."""
    logger.info("Defining security remediation tasks")
    remediation_tasks = []

    if info['patches'].get('updates_available'):
        remediation_tasks.append({
            'action': 'update_system',
            'description': 'Update the system to install available patches',
            'reason': 'System updates are available',
            'tags': ['security', 'updates']
        })

    firewall_active = False
    for firewall in info['firewall_status'].values():
        if firewall in ['active', 'configured']:
            firewall_active = True
            break

    if not firewall_active:
        remediation_tasks.append({
            'action': 'enable_firewall',
            'description': 'Enable or install a firewall',
            'reason': 'No active firewall detected',
            'tags': ['security', 'firewall']
        })

    if 'Port' not in info['ssh_config'] or info['ssh_config'].get('Port') == '22':
        remediation_tasks.append({
            'action': 'change_ssh_port',
            'description': 'Change SSH port from default',
            'reason': 'SSH is using default port 22 which might be insecure',
            'tags': ['security', 'ssh']
        })

    return remediation_tasks

def send_response(module, message, info, id_offset):
    """Generate a uniform response for the module with the given information."""
    logger.info("Sending security response with facts")
    remediation_tasks = define_remediation(info)
    module.exit_json(
        changed=False,
        msg=message,
        ansible_facts={
            'actions': remediation_tasks,
            'data': {'host': {'security': info}},
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

    logger.info("Starting security module execution")
    now = datetime.datetime.now()
    epoch = int(now.timestamp())
    message = f"Checking security status."

    info = assess_state()
    send_response(module, message, info, id_offset)

if __name__ == '__main__':
    main()