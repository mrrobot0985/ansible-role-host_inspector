#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import subprocess
import os
import json

def run_module():
    module = AnsibleModule(
        argument_spec=dict(),
        supports_check_mode=True
    )

    results = {
        "package_manager_proxy": check_package_manager_proxy(),
        "environment_proxy": check_environment_proxy(),
        "browser_proxy": {
            "firefox": check_firefox_proxy(),
            "brave": check_brave_proxy()
        },
        "wan_address": get_wan_address()
    }

    module.exit_json(changed=False, proxy_info=results)

def check_package_manager_proxy():
    proxy_settings = {}
    
    # Check for apt (Debian/Ubuntu)
    if os.path.exists('/etc/apt/apt.conf.d/'):
        for file in os.listdir('/etc/apt/apt.conf.d/'):
            if file.startswith('99'):
                with open(os.path.join('/etc/apt/apt.conf.d/', file), 'r') as f:
                    for line in f:
                        if 'Acquire::http::Proxy' in line or 'Acquire::https::Proxy' in line:
                            proxy = line.split('"')[1]
                            proxy_settings[file] = proxy

    # Check for yum (RedHat/CentOS)
    if os.path.exists('/etc/yum.conf'):
        with open('/etc/yum.conf', 'r') as f:
            for line in f:
                if 'proxy=' in line:
                    proxy_settings['yum'] = line.split('=')[1].strip()

    return proxy_settings

def check_environment_proxy():
    return {key: val for key, val in os.environ.items() if key.lower() in ['http_proxy', 'https_proxy', 'ftp_proxy']}

def check_firefox_proxy():
    firefox_profile = os.path.expanduser("~/.mozilla/firefox/")
    if os.path.isdir(firefox_profile):
        for dir in os.listdir(firefox_profile):
            if dir.endswith('.default-release'):
                prefs_file = os.path.join(firefox_profile, dir, 'prefs.js')
                if os.path.exists(prefs_file):
                    with open(prefs_file, 'r') as f:
                        prefs = f.read()
                        if 'network.proxy.type' in prefs:
                            proxy_type = prefs.split('network.proxy.type')[1].split(';')[0].strip().split('=')[1].strip()
                            proxy_settings = {
                                "type": "system" if proxy_type == "4" else "manual" if proxy_type == "1" else "none"
                            }
                            # Here you would add more detailed parsing if needed
                            return proxy_settings
    return {"error": "Firefox profile or prefs not found"}

def check_brave_proxy():
    brave_config_path = os.path.expanduser("~/.config/BraveSoftware/Brave-Browser/Default/Preferences")
    brave_proxy = {}
    if os.path.exists(brave_config_path):
        try:
            with open(brave_config_path, 'r') as f:
                prefs = json.load(f)
            proxy_config = prefs.get('brave.proxy', {})
            brave_proxy['type'] = proxy_config.get('mode', 'direct')
            if brave_proxy['type'] == 'fixed_servers':
                brave_proxy['http'] = proxy_config.get('proxy_server', {}).get('http', '')
                brave_proxy['https'] = proxy_config.get('proxy_server', {}).get('https', '')
                brave_proxy['ftp'] = proxy_config.get('proxy_server', {}).get('ftp', '')
        except Exception as e:
            brave_proxy['error'] = str(e)
    else:
        brave_proxy['error'] = "Brave configuration not found"
    return brave_proxy

def get_wan_address():
    try:
        # Using curl to fetch WAN IP address
        cmd = ["curl", "-s", "--max-time", "5", "https://api.ipify.org?format=json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)['ip']
    except subprocess.CalledProcessError as e:
        return {"error": f"Failed to retrieve WAN address: {e.stderr}"}
    except json.JSONDecodeError:
        return {"error": "Failed to decode WAN address response"}
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

if __name__ == '__main__':
    run_module()