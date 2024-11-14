#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import subprocess
import json
import os

def run_module():
    module = AnsibleModule(
        argument_spec=dict(),
        supports_check_mode=True
    )

    results = {
        "docker_info": check_docker_info(),
        "docker_daemon_config": get_docker_daemon_config(),
        "docker_runtime_info": get_docker_runtime_info(),
        "docker_environment": get_docker_environment()
    }

    module.exit_json(changed=False, docker_info=results)

def is_docker_installed():
    return os.path.exists('/usr/bin/docker') or os.path.exists('/usr/local/bin/docker')

def check_docker_info():
    if not is_docker_installed():
        return {"installed": False, "message": "Docker is not installed"}
    
    try:
        info = subprocess.check_output(['docker', 'info', '--format', '{{json .}}'], stderr=subprocess.DEVNULL).decode('utf-8')
        parsed_info = json.loads(info)
        return {
            "installed": True,
            "server_version": parsed_info.get('ServerVersion', 'Unknown'),
            "operating_system": parsed_info.get('OperatingSystem', 'Unknown'),
            "kernel_version": parsed_info.get('KernelVersion', 'Unknown')
        }
    except Exception as e:
        return {"installed": True, "error": str(e)}

def get_docker_daemon_config():
    if not is_docker_installed():
        return {"error": "Docker is not installed"}
    
    daemon_config = {}
    daemon_json_path = '/etc/docker/daemon.json'
    if os.path.exists(daemon_json_path):
        try:
            with open(daemon_json_path, 'r') as f:
                daemon_config = json.load(f)
            return {k: daemon_config[k] for k in ['debug', 'experimental', 'features', 'insecure-registries', 'log-driver'] if k in daemon_config}
        except json.JSONDecodeError:
            return {"error": "Failed to parse daemon.json"}
    else:
        return {"error": "daemon.json not found"}

def get_docker_runtime_info():
    if not is_docker_installed():
        return {"error": "Docker is not installed"}
    
    try:
        output = subprocess.check_output(['docker', 'info', '--format', '{{json .Runtimes}}'], stderr=subprocess.DEVNULL).decode('utf-8')
        runtime_info = json.loads(output)
        return {"runtimes": list(runtime_info.keys())}
    except subprocess.CalledProcessError as e:
        return {"error": f"Failed to get runtime info: {e.output.decode('utf-8')}"}

def get_docker_environment():
    if not is_docker_installed():
        return {"error": "Docker is not installed"}
    
    try:
        env_output = subprocess.check_output(['docker', 'version', '--format', '{{json .Client.Env}}'], stderr=subprocess.DEVNULL).decode('utf-8')
        env = json.loads(env_output)
        return {
            "http_proxy": env.get('HTTP_PROXY', ''), 
            "https_proxy": env.get('HTTPS_PROXY', ''), 
            "no_proxy": env.get('NO_PROXY', '')
        }
    except subprocess.CalledProcessError as e:
        return {"error": f"Failed to get environment info: {e.output.decode('utf-8')}"}

if __name__ == '__main__':
    run_module()