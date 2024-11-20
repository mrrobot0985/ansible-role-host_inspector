#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ansible.module_utils.basic import AnsibleModule
import os
import json
import socket
import http.client
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

def _set_speech(id=0, speaker_id=0, message=None, remediation_tasks=None):
    """Set up a speech structure with sentences, combined remediation tasks, and tags."""
    objects = []
    if message:
        objects.append({ 
            "id": str(id), 
            "text": message, 
            "speaker_id": str(speaker_id), 
            "output_file": f"/tmp/internet_status_report_{id}.wav", 
            "tags": ["initiation", "internet"]
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
            "output_file": f"/tmp/internet_status_report_{id}.wav",
            "tags": list(actions_tags)
        })
        id += 1

    objects.append({ 
        "id": str(id), 
        "text": "Internet system analysis completed.", 
        "speaker_id": str(speaker_id), 
        "output_file": f"/tmp/internet_status_report_{id}.wav",
        "tags": ["system", "internet", "status"]
    })
    id += 1

    return {
        "next_id": id,
        "objects": objects
    }

def check_package_manager_proxy():
    """Check for proxy settings in package managers."""
    proxy_settings = {}
    if os.path.exists('/etc/apt/apt.conf.d/'):
        for file in os.listdir('/etc/apt/apt.conf.d/'):
            if file.startswith('99'):
                with open(os.path.join('/etc/apt/apt.conf.d/', file), 'r') as f:
                    for line in f:
                        if any(key in line for key in ['Acquire::http::Proxy', 'Acquire::https::Proxy']):
                            proxy = line.split('"')[1]
                            proxy_settings[file] = proxy
    if os.path.exists('/etc/yum.conf'):
        with open('/etc/yum.conf', 'r') as f:
            for line in f:
                if 'proxy=' in line:
                    proxy_settings['yum'] = line.split('=')[1].strip()
    return proxy_settings

def check_environment_proxy():
    """Check for proxy settings in the environment variables."""
    return {env_var: os.environ[env_var] for env_var in ['http_proxy', 'https_proxy', 'ftp_proxy'] if env_var in os.environ}

def check_browser_proxy():
    """Check for proxy settings in browsers."""
    browsers = {"firefox": check_firefox_proxy(), "brave": check_brave_proxy()}
    return {browser: status for browser, status in browsers.items() if status != {"error": f"{browser.capitalize()} not installed"}}

def check_firefox_proxy():
    """Check Firefox for proxy settings."""
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
                            return {
                                "installed": True,
                                "type": "system" if proxy_type == "4" else "manual" if proxy_type == "1" else "none"
                            }
    return {"error": "Firefox not installed"}

def check_brave_proxy():
    """Check Brave for proxy settings."""
    brave_config_path = os.path.expanduser("~/.config/BraveSoftware/Brave-Browser/Default/Preferences")
    if os.path.exists(brave_config_path):
        try:
            with open(brave_config_path, 'r') as f:
                prefs = json.load(f)
            proxy_config = prefs.get('brave.proxy', {})
            return {
                "installed": True,
                "type": proxy_config.get('mode', 'direct'),
                "http": proxy_config.get('proxy_server', {}).get('http', ''),
                "https": proxy_config.get('proxy_server', {}).get('https', ''),
                "ftp": proxy_config.get('proxy_server', {}).get('ftp', '')
            }
        except Exception as e:
            return {"error": f"Failed to read Brave configuration: {str(e)}"}
    return {"error": "Brave not installed"}

def get_wan_address():
    """Retrieve the public WAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("1.1.1.1", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        try:
            return socket.gethostbyname('myip.opendns.com')
        except socket.gaierror:
            try:
                conn = http.client.HTTPConnection("ipinfo.io", timeout=10)
                conn.request("GET", "/ip")
                response = conn.getresponse()
                if response.status == 200:
                    return response.read().decode().strip()
                else:
                    return {"error": f"HTTP request failed with status: {response.status}"}
            except (http.client.HTTPException, ConnectionError) as e:
                return {"error": f"Failed to retrieve WAN address using HTTP: {str(e)}"}

        return {"error": "Failed to retrieve WAN address using DNS methods"}
    except Exception as e:
        return {"error": f"Failed to retrieve WAN address: {str(e)}"}

def define_remediation(info):
    """Define remediation tasks based on internet configuration checks."""
    remediation_tasks = []
    
    # WAN Address check
    if not info.get('wan_address') or (isinstance(info['wan_address'], dict) and 'error' in info['wan_address']):
        remediation_tasks.append({
            'action': 'check_internet',
            'description': "Check internet connectivity",
            'reason': "Failed to retrieve WAN address",
            'filepath': None,
            'tags': ['internet', 'connectivity'],
        })
    
    # Check for proxy settings only if WAN address could not be retrieved
    if not info.get('wan_address') or (isinstance(info['wan_address'], dict) and 'error' in info['wan_address']):
        if not info.get('package_manager_proxy'):
            remediation_tasks.append({
                'action': 'check_package_manager_proxy',
                'description': "Check package manager proxy settings",
                'reason': "No proxy settings found",
                'filepath': "/etc/apt/apt.conf.d/" if os.path.exists('/etc/apt/apt.conf.d/') else "/etc/yum.conf",
                'tags': ['internet', 'package_manager', 'proxy'],
            })
        if not info.get('environment_proxy'):
            remediation_tasks.append({
                'action': 'set_environment_proxy',
                'description': "Set environment proxy variables",
                'reason': "No environment proxy variables set",
                'filepath': "/etc/environment",
                'tags': ['internet', 'environment', 'proxy'],
            })
    
    return remediation_tasks

def send_response(module, message, results, id_offset):
    """Generate a uniform response for the module with the given information."""
    logger.info("Sending Internet status response with facts")
    remediation_tasks = define_remediation(results)
    module.exit_json(
        changed=False,
        msg=message,
        ansible_facts={
            'actions': remediation_tasks,
            'data': {'host': {'internet_info': results}},
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
        supports_check_mode=True
    )

    id_offset = module.params['id_offset']
    log_path = module.params['log_path']

    global logger
    logger = _setup_logging(log_path)

    logger.info("Starting Internet system check module execution")
    
    now = datetime.datetime.now()
    epoch = int(now.timestamp())
    message = f"Checking Internet."

    results = {
        "package_manager_proxy": check_package_manager_proxy(),
        "environment_proxy": check_environment_proxy(),
        "browser_proxy": check_browser_proxy(),
        "wan_address": get_wan_address()
    }

    send_response(module, message, results, id_offset)

if __name__ == '__main__':
    main()