#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import subprocess
import json
import netifaces
import platform

def run_module():
    module = AnsibleModule(
        argument_spec=dict(),
        supports_check_mode=True
    )

    try:
        results = {
            "interfaces": get_interface_info(),
            "routes": get_route_info(),
            "dns": get_dns_info()
        }
        module.exit_json(changed=False, network_info=results)
    except Exception as e:
        module.fail_json(msg=str(e))

def get_interface_info():
    interfaces = {}
    for interface in netifaces.interfaces():
        if_info = netifaces.ifaddresses(interface)
        interfaces[interface] = {
            "ipv4": if_info.get(netifaces.AF_INET, [{"addr": "N/A"}])[0].get('addr', "N/A"),
            "ipv6": if_info.get(netifaces.AF_INET6, [{"addr": "N/A"}])[0].get('addr', "N/A") if netifaces.AF_INET6 in if_info else "N/A",
            "mac": if_info.get(netifaces.AF_LINK, [{"addr": "N/A"}])[0].get('addr', "N/A")
        }
        # Get detailed interface info using 'ip' command for Linux systems
        if platform.system() == "Linux":
            try:
                ip_output = subprocess.check_output(['ip', 'addr', 'show', interface]).decode('utf-8')
                interfaces[interface].update(parse_ip_output(ip_output))
            except subprocess.CalledProcessError:
                # If 'ip' command fails, continue with basic info
                pass
    return interfaces

def parse_ip_output(ip_output):
    interface_info = {}
    lines = ip_output.split('\n')
    for line in lines:
        if 'mtu' in line:
            interface_info['mtu'] = line.split('mtu')[1].split()[0].strip()
        elif 'inet ' in line:
            interface_info['ipv4_cidr'] = line.split('inet ')[1].split()[0].strip()
        elif 'inet6 ' in line:
            interface_info['ipv6_cidr'] = line.split('inet6 ')[1].split()[0].strip()
        elif 'broadcast' in line:
            interface_info['broadcast'] = line.split('brd')[1].split()[0].strip()
        elif 'link/ether' in line:
            interface_info['mac'] = line.split('link/ether')[1].split()[0].strip()
    return interface_info

def get_route_info():
    if platform.system() == "Linux":
        try:
            route_output = subprocess.check_output(['ip', 'route']).decode('utf-8')
            return parse_route_output(route_output)
        except subprocess.CalledProcessError:
            return {"error": "Failed to retrieve routing information"}
    else:
        return {"note": "Route information collection not implemented for this OS"}

def parse_route_output(route_output):
    routes = []
    for line in route_output.split('\n'):
        if not line:
            continue
        parts = line.split()
        route = {
            "destination": parts[0],
            "via": parts[2] if "via" in parts else "N/A",
            "dev": parts[4] if "dev" in parts else "N/A",
            "metric": parts[parts.index('metric') + 1] if 'metric' in parts else "N/A"
        }
        routes.append(route)
    return routes

def get_dns_info():
    if platform.system() == "Linux":
        try:
            with open('/etc/resolv.conf', 'r') as f:
                dns_servers =[line.split()[1] for line in f if line.startswith('nameserver')]
            return {"dns_servers": dns_servers}
        except FileNotFoundError:
            return {"error": "resolv.conf file not found"}
    else:
        return {"note": "DNS information collection not implemented for this OS"}

if __name__ == '__main__':
    run_module()