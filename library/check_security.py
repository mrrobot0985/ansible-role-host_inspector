#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import subprocess
import re
import os
import platform

def run_module():
    module = AnsibleModule(
        argument_spec=dict(),
        supports_check_mode=True
    )

    results = {
        "os": get_os_info(),
        "ssh_config": check_ssh_config(),
        "firewall_status": check_firewall_status(),
        "patches": check_patches()
    }

    module.exit_json(changed=False, security_status=results)

def get_os_info():
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "node": platform.node()
    }

def check_ssh_config():
    ssh_config = {}
    try:
        with open('/etc/ssh/sshd_config', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.split(None, 1)
                    ssh_config[key.strip()] = value.strip()
    except FileNotFoundError:
        ssh_config = {"error": "sshd_config not found"}
    return ssh_config

def check_firewall_status():
    firewall_status = {}
    if platform.system() == "Linux":
        # Check for iptables
        try:
            output = subprocess.check_output(['iptables', '-L'], stderr=subprocess.STDOUT).decode('utf-8')
            firewall_status["iptables"] = "active" if "Chain INPUT" in output else "inactive"
        except subprocess.CalledProcessError:
            firewall_status["iptables"] = "unknown"

        # Check for UFW
        if os.path.exists('/usr/sbin/ufw'):
            try:
                ufw_status = subprocess.check_output(['ufw', 'status'], stderr=subprocess.STDOUT).decode('utf-8')
                firewall_status["ufw"] = "active" if "Status: active" in ufw_status else "inactive"
                firewall_status["ufw_rules"] = parse_ufw_rules(ufw_status)
            except subprocess.CalledProcessError:
                firewall_status["ufw"] = "unknown"
                firewall_status["ufw_rules"] = []

        # Check for firewalld
        try:
            output = subprocess.check_output(['systemctl', 'is-active', 'firewalld'], stderr=subprocess.STDOUT).decode('utf-8').strip()
            firewall_status["firewalld"] = output
        except subprocess.CalledProcessError:
            firewall_status["firewalld"] = "unknown"
    return firewall_status

def parse_ufw_rules(ufw_status):
    lines = ufw_status.split('\n')
    rules = []
    for line in lines:
        if line.strip() and not line.startswith('Status:') and not line.startswith('To') and not line.startswith('--'):
            parts = line.split()
            rule = {
                "number": parts[0] if parts[0].isdigit() else None,
                "action": parts[2] if len(parts) > 2 else None,
                "direction": parts[3] if len(parts) > 3 else None,
                "port": parts[1] if parts[1].isdigit() else None,
                "protocol": parts[4] if len(parts) > 4 and parts[4] in ['tcp', 'udp'] else None,
                "from_ip": parts[5] if len(parts) > 5 else None,
                "comment": ' '.join(parts[parts.index('#')+1:]) if '#' in parts else None
            }
            rules.append(rule)
    return rules

def check_patches():
    patches = {}
    if platform.system() == "Linux":
        if os.path.exists('/usr/bin/yum'):
            # For RedHat/CentOS
            try:
                output = subprocess.check_output(['yum', 'check-update'], stderr=subprocess.STDOUT).decode('utf-8')
                patches['updates_available'] = "updates_available" in output
                patches['yum_output'] = output
            except subprocess.CalledProcessError:
                patches['error'] = "Failed to run yum check-update"
        elif os.path.exists('/usr/bin/apt-get'):
            # For Debian/Ubuntu
            try:
                output = subprocess.check_output(['apt-get', 'upgrade', '-s'], stderr=subprocess.STDOUT).decode('utf-8')
                patches['updates_available'] = "The following packages have been kept back" in output or "Inst" in output
                patches['apt_output'] = output
            except subprocess.CalledProcessError:
                patches['error'] = "Failed to run apt-get upgrade -s"
    return patches

if __name__ == '__main__':
    run_module()