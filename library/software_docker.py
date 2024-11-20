#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ansible.module_utils.basic import AnsibleModule
import subprocess
import json
import os
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
            "output_file": f"/tmp/docker_status_report_{id}.wav", 
            "tags": ["initiation", "docker"]
        })
        id += 1

    # Combine all remediation tasks into one message with tags
    if remediation_tasks:
        actions_text = "Recommended actions are: "
        actions_tags = set()
        for task in remediation_tasks:
            actions_text += f"{task['description']} for {task['tags'][-1]} due to {task['reason']}. "
            actions_tags.update(task['tags'])
        
        objects.append({
            "id": str(id),
            "text": actions_text,
            "speaker_id": str(speaker_id),
            "output_file": f"/tmp/docker_status_report_{id}.wav",
            "tags": list(actions_tags)
        })
        id += 1

    objects.append({ 
        "id": str(id), 
        "text": "Docker system analysis completed.", 
        "speaker_id": str(speaker_id), 
        "output_file": f"/tmp/docker_status_report_{id}.wav",
        "tags": ["system", "docker", "status"]
    })
    id += 1

    return {
        "next_id": id,
        "objects": objects
    }

def _run_cmd(command, check=True, text=True):
    """Run a shell command with error handling."""
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=check, text=text)
        return result.stdout.strip(), None
    except subprocess.CalledProcessError as e:
        return None, str(e)

def check_system_info():
    """Retrieve basic system information."""
    return {
        "os": os.name,
        "user_id": os.getuid(),
        "username": os.getlogin()
    }

def is_docker_installed():
    """Check if Docker is installed by looking for the docker binary."""
    return os.path.exists('/usr/bin/docker') or os.path.exists('/usr/local/bin/docker')

def check_docker_info():
    """Retrieve Docker server information."""
    if not is_docker_installed():
        return {
            "installed": False,
            "remediation_tasks": [
                {"action": "install_docker", "description": "Install Docker", "reason": "Docker is not installed", "tags": ["system", "docker"]}
            ]
        }
    
    info, error = _run_cmd('docker info --format json')
    if info:
        try:
            parsed_info = json.loads(info)
            return {
                "installed": True,
                "server_version": parsed_info.get('ServerVersion', 'Unknown'),
                "operating_system": parsed_info.get('OperatingSystem', 'Unknown'),
                "kernel_version": parsed_info.get('KernelVersion', 'Unknown'),
                "remediation_tasks": []
            }
        except json.JSONDecodeError:
            return {
                "installed": True,
                "error": "Failed to parse Docker info JSON",
                "remediation_tasks": [
                    {"action": "check_docker_json_output", "description": "Ensure Docker info outputs valid JSON", "reason": "JSON parsing error", "tags": ["system", "docker"]}
                ]
            }
    else:
        return {
            "installed": True,
            "error": f"Failed to get Docker info: {error}",
            "remediation_tasks": [
                {"action": "check_docker_installation", "description": "Check Docker installation", "reason": f"Command failed with error: {error}", "tags": ["system", "docker"]}
            ]
        }

def get_docker_daemon_config():
    """Get Docker daemon configuration from daemon.json."""
    if not is_docker_installed():
        return {"error": "Docker is not installed", "remediation_tasks": []}

    daemon_json_paths = ['/etc/docker/daemon.json', os.path.expanduser('~/.config/docker/daemon.json')]
    for path in daemon_json_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    config = json.load(f)
                return {
                    "daemon_config": {k: config.get(k, "Not set") for k in ['debug', 'experimental', 'features', 'insecure-registries', 'log-driver']},
                    "remediation_tasks": []
                }
            except json.JSONDecodeError:
                return {"error": f"Failed to parse daemon.json at {path}", "remediation_tasks": [
                    {"action": "fix_daemon_json", "description": "Fix or replace daemon.json", "reason": "daemon.json is not valid JSON", "tags": ["system", "docker", "config"]}
                ]}
    return {"message": "daemon.json not found in any expected location", "remediation_tasks": []}

def get_docker_runtime_info():
    """Get information about Docker runtimes."""
    if not is_docker_installed():
        return {"error": "Docker is not installed", "remediation_tasks": []}
    
    runtime_info, error = _run_cmd('docker info --format "{{json .Runtimes}}"')
    if runtime_info:
        return {"runtimes": list(json.loads(runtime_info).keys()), "remediation_tasks": []}
    else:
        return {"error": f"Failed to get runtime info: {error}", "remediation_tasks": []}

def get_docker_environment():
    """Retrieve Docker environment variables related to proxy settings."""
    if not is_docker_installed():
        return {"error": "Docker is not installed", "remediation_tasks": []}
    
    info_output, error = _run_cmd('docker info --format json')
    if info_output:
        try:
            full_info = json.loads(info_output)
            env_vars = full_info.get('Env', [])
            env_dict = dict(var.split('=', 1) for var in env_vars if '=' in var)
            return {
                "environment": {
                    "http_proxy": env_dict.get('HTTP_PROXY', ''), 
                    "https_proxy": env_dict.get('HTTPS_PROXY', ''), 
                    "no_proxy": env_dict.get('NO_PROXY', '')
                },
                "remediation_tasks": []
            }
        except json.JSONDecodeError:
            return {
                "environment": {},
                "error": f"Failed to parse JSON from 'docker info': {error}",
                "remediation_tasks": [
                    {"action": "check_docker_json_output", "description": "Ensure Docker info outputs valid JSON", "reason": "JSON parsing error", "tags": ["system", "docker", "environment"]}
                ]
            }
    else:
        return {
            "environment": {},
            "error": f"Failed to get Docker environment info: {error}",
            "remediation_tasks": [
                {"action": "check_docker_info", "description": "Check Docker info command", "reason": "Docker info command failed to execute or return JSON", "tags": ["system", "docker", "environment"]}
            ]
        }

def check_rootless_setup():
    """Check for rootless Docker setup."""
    if not is_docker_installed():
        return {
            "rootless_setup": {"error": "Docker is not installed"},
            "remediation_tasks": []
        }

    rootless_setup_info = {}
    if 'DOCKER_HOST' in os.environ and 'user/' in os.environ['DOCKER_HOST']:
        rootless_setup_info = {
            "rootless": True,
            "user_uid": os.environ['DOCKER_HOST'].split('/')[3] if os.environ['DOCKER_HOST'].split('/') else None,
            "required_files": {},
            "daemon_running": False,
            "remediation_tasks": []
        }
        
        rootless_files = {
            'daemon.json': '~/.config/docker/daemon.json',
            '.dockerenv': '~/.docker/.dockerenv',
            'docker.service': '~/.config/systemd/user/docker.service'
        }
        
        for file, path in rootless_files.items():
            full_path = os.path.expanduser(path)
            file_info = rootless_setup_info["required_files"][file] = {
                "present": os.path.exists(full_path), 
                "path": full_path
            }
            
            if file == 'daemon.json':
                try:
                    with open(full_path, 'r') as f:
                        json.load(f)
                    file_info["valid"] = True
                except (json.JSONDecodeError, FileNotFoundError):
                    file_info["valid"] = False
                    rootless_setup_info["remediation_tasks"].append({
                        "action": "fix_daemon_json", 
                        "description": "Fix or replace daemon.json", 
                        "reason": "daemon.json is not valid JSON or not found",
                        'tags': ['docker', 'rootless', 'daemon'],
                        "type": "file_creation",
                        "_ansible_module": 'copy',
                        "_ansible_args": {
                            'dest': full_path,
                            'content': '{}'
                        }
                    })
            else:
                if not file_info["present"]:
                    template_name = os.path.basename(file_info['path']) + '.j2'
                    template_path = os.path.join('templates', template_name)
                    action_type = 'jinja' if os.path.exists(template_path) else 'copy'
                    remediation_task = {
                        "action": "create_or_correct_file",
                        "description": f"Ensure {file} exists",
                        "reason": f"File {file} is missing",
                        "file_path": full_path,
                        "type": action_type,
                        'tags': ['docker', 'rootless', 'daemon'],
                        "_ansible_module": 'template' if action_type == 'jinja' else 'copy',
                        "_ansible_args": {
                            'dest': file_info['path'],
                            'src': template_name if action_type == 'jinja' else ''
                        }
                    }
                    if action_type == 'copy':
                        remediation_task['_ansible_args']['content'] = ''
                    rootless_setup_info["remediation_tasks"].append(remediation_task)

        # Check if Docker daemon is running in rootless mode
        process = subprocess.Popen(['ps', 'aux'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = process.communicate()
        rootless_setup_info["daemon_running"] = any(line for line in stdout.decode('utf-8').split('\n') if 'dockerd' in line and 'root' not in line)

        # Check for missing rootlesskit or dockerd-rootless.sh
        if any((not file_info.get("present", False) for file_info in rootless_setup_info["required_files"].values() if file_info.get("path") in ["/usr/bin/rootlesskit", "/usr/bin/dockerd-rootless.sh"])):
            rootless_setup_info["remediation_tasks"].append({
                "action": "install_rootless_components", 
                "description": "Install Rootless Docker Components", 
                "reason": "Required rootless Docker components are missing",
                "type": "shell",
                'tags': ['docker', 'rootlesskit'],
                "command": "curl",
                "arguments": ["-fsSL", "https://get.docker.com/rootless", "|", "sh"]
            })

    else:
        rootless_setup_info = {"rootless": False, "message": "DOCKER_HOST does not indicate rootless mode."}

    return {"rootless_setup": rootless_setup_info}

def define_remediation(info):
    """Collect remediation tasks from all sections of the docker_info and return them under 'actions'."""
    actions = []
    sections = ['daemon_config', 'environment', 'runtimes', 'rootless_setup']
    for section in sections:
        if section in info:
            if isinstance(info[section], dict) and 'remediation_tasks' in info[section]:
                actions.extend(info[section].pop('remediation_tasks', []))
            elif 'rootless_setup' in info[section] and 'remediation_tasks' in info[section]['rootless_setup']:
                actions.extend(info[section]['rootless_setup'].pop('remediation_tasks', []))
    return actions

def send_response(module, message, info, id_offset):
    """Generate a uniform response for the module with the given information."""
    logger.info("Sending Docker status response with facts")
    actions = define_remediation(info)
    # Remove the remediation_tasks from the info dict as they have been moved to actions
    for section in ['daemon_config', 'environment', 'runtimes', 'rootless_setup']:
        if section in info and 'remediation_tasks' in info[section]:
            del info[section]['remediation_tasks']
        if 'rootless_setup' in info and 'remediation_tasks' in info['rootless_setup']:
            del info['rootless_setup']['remediation_tasks']

    module.exit_json(
        changed=False,
        msg=message,
        ansible_facts={
            'actions': actions,
            'data': {'host': {'docker_info': info}},
            'speech': _set_speech(id_offset, message=message, remediation_tasks=actions),
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

    logger.info("Starting Docker system check module execution")
    
    now = datetime.datetime.now()
    epoch = int(now.timestamp())
    message = f"Checking Docker setup."

    docker_info = {
        **check_docker_info(),
        **get_docker_daemon_config(),
        **get_docker_environment(),
        **get_docker_runtime_info(),
        **check_rootless_setup(),
        "system_info": check_system_info()
    }

    send_response(module, message, docker_info, id_offset)

if __name__ == '__main__':
    main()