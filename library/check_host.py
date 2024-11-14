#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import os
import platform
import locale
import subprocess

def run_module():
    module = AnsibleModule(
        argument_spec={},
        supports_check_mode=True
    )

    result = {
        "reboot_required": check_reboot_required(),
        "system_locale": get_system_locale(),
        "system_language": get_system_language(),
        "os_info": get_os_info(),
        "uptime": get_uptime(),
        "disk_usage": get_disk_usage(),
        "cpu_count": get_cpu_count(),
        "python_version": platform.python_version(),
        "memory_info": get_memory_info(),
        "swap_info": get_swap_info(),
        "patches": get_patch_info()  # Fetching patch information with statistics
    }

    module.exit_json(changed=False, host_info=result)

def check_reboot_required():
    # Check for reboot requirement on Debian-based systems
    return os.path.exists('/var/run/reboot-required')

def get_system_locale():
    try:
        return locale.getlocale()
    except locale.Error:
        return "Locale not set"

def get_system_language():
    try:
        return subprocess.check_output(['echo', '$LANG'], shell=True).decode('utf-8').strip()
    except subprocess.CalledProcessError:
        return "Unable to determine language"

def get_os_info():
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "node": platform.node()
    }

def get_uptime():
    try:
        with open('/proc/uptime', 'r') as f:
            return int(float(f.read().split()[0]))
    except FileNotFoundError:
        try:
            output = subprocess.check_output(['uptime', '-p'], shell=True).decode('utf-8').strip()
            if 'days' in output:
                days = int(output.split('days')[0])
                return days * 86400
            return 0
        except:
            return "Unable to get uptime"

def get_disk_usage():
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        return {
            "total": total,
            "used": used,
            "free": free
        }
    except:
        return "Unable to get disk usage"

def get_cpu_count():
    import multiprocessing
    return multiprocessing.cpu_count()

def get_memory_info():
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.readlines()
        
        mem_total = int(meminfo[0].split()[1])  # MemTotal
        mem_free = int(meminfo[1].split()[1])  # MemFree
        mem_available = int(meminfo[2].split()[1])  # MemAvailable
        
        return {
            "total": mem_total * 1024,
            "free": mem_free * 1024,
            "available": mem_available * 1024
        }
    except (FileNotFoundError, IndexError):
        return "Unable to get memory info"

def get_swap_info():
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.readlines()
        
        # Finding SwapTotal and SwapFree
        swap_info =[line for line in meminfo if line.startswith(('SwapTotal', 'SwapFree'))]
        if len(swap_info) == 2:
            swap_total = int(swap_info[0].split()[1])
            swap_free = int(swap_info[1].split()[1])
            return {
                "total": swap_total * 1024,
                "free": swap_free * 1024
            }
        else:
            return "No swap information available"
    except (FileNotFoundError, IndexError):
        return "Unable to get swap info"

import re

def get_patch_info():
    try:
        apt_output = subprocess.check_output(['apt-get', 'upgrade', '--simulate'], stderr=subprocess.STDOUT).decode('utf-8')
        
        apt_info = {
            "apt_output": {
                "upgraded": 0,
                "newly_installed": 0,
                "to_remove": 0,
                "not_upgraded": 0,
                "upgradable": 0
            },
            "updates_available": False
        }

        # Extract the summary stats
        summary_match = re.search(r'(\d+) upgraded, (\d+) newly installed, (\d+) to remove and (\d+) not upgraded', apt_output)
        if summary_match:
            apt_info['apt_output']['upgraded'] = int(summary_match.group(1))
            apt_info['apt_output']['newly_installed'] = int(summary_match.group(2))
            apt_info['apt_output']['to_remove'] = int(summary_match.group(3))
            apt_info['apt_output']['not_upgraded'] = int(summary_match.group(4))

            # 'upgradable' might be considered as anything that could be updated or installed
            apt_info['apt_output']['upgradable'] = sum(int(summary_match.group(i)) for i in[1, 2, 4])  # sum of upgraded, newly_installed, and not_upgraded

            # If any of the above are greater than 0, we consider updates available
            apt_info['updates_available'] = any(apt_info['apt_output'].values())

        return {"patches": apt_info}
    except subprocess.CalledProcessError as e:
        return {"patches": {"error": str(e)}}
    except Exception as e:
        return {"patches": {"error": f"An unexpected error occurred: {str(e)}"}}

if __name__ == '__main__':
    run_module()