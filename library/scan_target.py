#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import subprocess
import json
import time
import socket

def run_module():
    module = AnsibleModule(
        argument_spec=dict(
            targets=dict(type='list', required=True),
            timeout=dict(type='int', default=60),
            ports=dict(type='str', default='1-1024')
        ),
        supports_check_mode=True
    )

    results = {}
    if not is_nmap_available():
        for target in module.params['targets']:
            results[target] = {"status": "nmap_not_available", "open_ports": [], "scan_time": 0}
    else:
        for target in module.params['targets']:
            if target == 'localhost' and module.params.get('ansible_connection') == 'local':
                # If localhost is defined as local in inventory, skip the scan
                results[target] = {"status": "local", "open_ports": [], "scan_time": 0}
            else:
                target_ip = get_local_ip() if target == 'localhost' else target
                scan_result = nmap_scan(target_ip, module.params['ports'], module.params['timeout'])
                results[target] = scan_result if scan_result else {"status": "error", "open_ports": [], "scan_time": 0}

    module.exit_json(changed=False, scan_results=results)

def is_nmap_available():
    try:
        subprocess.run(['nmap', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def nmap_scan(target, ports, timeout):
    start_time = time.time()
    try:
        cmd = ['nmap', '-T4', '-Pn', '-p', ports, target, '-oX', '-']
        output = subprocess.check_output(cmd, timeout=timeout, stderr=subprocess.PIPE, universal_newlines=True)
        end_time = time.time()

        try:
            from xml.etree import ElementTree as ET
            root = ET.fromstring(output)
            host = root.find('host')
            if host.find('status').get('state') == 'up':
                open_ports =[port.get('portid') for port in host.findall('.//port') if port.find('state').get('state') == 'open']
                return {
                    "status": "up",
                    "open_ports": open_ports,
                    "scan_time": end_time - start_time
                }
            else:
                return {"status": "down", "open_ports": [], "scan_time": end_time - start_time}
        except ET.ParseError:
            return {"status": "error", "open_ports": [], "scan_time": end_time - start_time}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "open_ports": [], "scan_time": timeout}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": e.output.strip(), "open_ports": [], "scan_time": time.time() - start_time}

if __name__ == '__main__':
    run_module()