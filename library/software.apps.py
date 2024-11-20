#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ansible.module_utils.basic import AnsibleModule
import os
import re
import subprocess
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
            "output_file": f"/tmp/app_check_report_{id}.wav", 
            "tags": ["initiation"]
        })
        id += 1

    # Combine all remediation tasks into one message with tags
    if remediation_tasks:
        actions_text = "Recommended actions are: "
        actions_tags = set()
        for task in remediation_tasks:
            actions_text += f"{task['action']} for {task['tags'][-1]} due to {task['reason']}. "
            actions_tags.update(task['tags'])
        
        objects.append({
            "id": str(id),
            "text": actions_text,
            "speaker_id": str(speaker_id),
            "output_file": f"/tmp/app_check_report_{id}.wav",
            "tags": list(actions_tags)
        })
        id += 1

    objects.append({ 
        "id": str(id), 
        "text": "Application check completed.", 
        "speaker_id": str(speaker_id), 
        "output_file": f"/tmp/app_check_report_{id}.wav",
        "tags": ["system", "software"]
    })
    id += 1

    return {
        "next_id": id,
        "objects": objects
    }

def check_app_installed(app_name):
    """Check if the specified application is installed on the system and return its version or None."""
    try:
        # First, check if the application exists in PATH
        subprocess.run(['which', app_name], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Application exists, let's try to get its version
        try:
            # This assumes most applications have a --version flag or similar
            result = subprocess.run([app_name, '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            
            # Parse the version from the output
            # This is a very basic approach and might need customization for different applications
            version_output = result.stdout.strip()
            version_match = re.search(r'\d+(\.\d+)+', version_output)
            version = version_match.group(0) if version_match else None
            logger.info(f"{app_name} version: {version}")
            return version
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, AttributeError):
            logger.warning(f"Could not determine version for {app_name}, assuming installed")
            return "Installed - Version unknown"
    except subprocess.CalledProcessError:
        logger.info(f"{app_name} not found in PATH")
    
    # If not found in PATH, proceed with package manager checks
    if os.path.exists("/usr/bin/dpkg-query"):
        cmd = ["dpkg-query", "-W", "-f='${Version}'", app_name]
        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logger.info(f"Checking {app_name} with dpkg-query: {result.stdout}")
            return result.stdout.strip() or "Installed - Version unknown"
        except subprocess.CalledProcessError as e:
            logger.error(f"dpkg-query failed for {app_name}: {e.stderr}")
            return None

    # For RedHat-based systems (CentOS, Fedora)
    elif os.path.exists("/usr/bin/rpm"):
        cmd = ["rpm", "-q", "--queryformat", "%{VERSION}", app_name]
        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logger.info(f"Checking {app_name} with rpm: {result.stdout}")
            return result.stdout.strip() or "Installed - Version unknown"
        except subprocess.CalledProcessError as e:
            logger.error(f"rpm query failed for {app_name}: {e.stderr}")
            return None

    # For macOS, pkgutil doesn't provide a straightforward version check, so we'll just check if it's installed
    elif os.path.exists("/usr/bin/pkgutil"):
        cmd = ["pkgutil", "--pkg-info", app_name]
        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logger.info(f"Checking {app_name} with pkgutil: {result.stdout}")
            return "Installed - Version unknown"
        except subprocess.CalledProcessError as e:
            logger.error(f"pkgutil failed for {app_name}: {e.stderr}")
            return None

    # If none of the above match, we can't check for this app or it's not in a known package manager
    logger.warning(f"Unable to check for {app_name} as no supported package manager was found")
    return None

def define_remediation(app_info):
    """Define remediation tasks based on app installation information."""
    remediation_tasks = []
    
    for app, status in app_info.items():
        if not status or status == "Unknown":
            remediation_tasks.append({
                'action': 'install_app',
                'description': f"Install or verify the installation of {app}",
                'reason': f"{app} is either not installed or its status is unknown",
                'tags': ['system', 'software', app]
            })
    
    return remediation_tasks

def send_response(module, message, app_info, id_offset):
    """Generate a uniform response for the module with the given information."""
    remediation_tasks = define_remediation(app_info)
    logger.info("Sending application check response with facts")
    module.exit_json(
        changed=False,
        msg=message,
        ansible_facts={
            'actions': remediation_tasks,
            'data': {'host': {'app_info': app_info}},
            'speech': _set_speech(id_offset, message=message, remediation_tasks=remediation_tasks),
        }
    )

def main():
    """Main function to run the Ansible module."""
    module = AnsibleModule(
        argument_spec=dict(
            apps=dict(type='list', required=True),
            id_offset=dict(default=0, type='int', required=False),
            log_path=dict(type='str', required=False)
        ),
        supports_check_mode=True
    )

    id_offset = module.params['id_offset']
    log_path = module.params['log_path']

    global logger
    logger = _setup_logging(log_path)

    logger.info("Starting application check module execution")
    
    now = datetime.datetime.now()
    epoch = int(now.timestamp())
    message = f"Checking applications."

    app_info = {app: check_app_installed(app) for app in module.params['apps']}
    send_response(module, message, app_info, id_offset)

if __name__ == '__main__':
    main()