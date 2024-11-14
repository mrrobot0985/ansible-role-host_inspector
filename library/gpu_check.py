#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import subprocess
import json

def run_module():
    module = AnsibleModule(
        argument_spec=dict(),
        supports_check_mode=True
    )

    results = {
        "gpu_details": get_gpu_details(),
        "nvidia_docker": check_nvidia_docker()  # Keeping this for Docker-related info
    }

    module.exit_json(changed=False, gpu_info=results)

def get_gpu_details():
    try:
        # Query for specific GPU information
        gpu_query = subprocess.check_output(['nvidia-smi', '--query-gpu=index,name,uuid,driver_version,memory.total', '--format=csv,noheader'], stderr=subprocess.DEVNULL).decode('utf-8')
        gpu_details = []
        for line in gpu_query.split('\n'):
            if not line.strip():  # Skip empty lines
                continue
            index, name, uuid, driver_version, memory_total = line.split(', ')
            gpu_details.append({
                "index": index,
                "name": name,
                "uuid": uuid,
                "driver_version": driver_version,
                "memory_total": memory_total
            })
        return gpu_details
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []  # Return an empty list if nvidia-smi is not available or fails

def check_nvidia_docker():
    nvidia_docker_info = {
        "installed": False,
        "runtime_available": False,
        "config": {}
    }

    try:
        # Check if NVIDIA Container Toolkit is installed
        dpkg_list = subprocess.check_output(['dpkg', '-l'], stderr=subprocess.DEVNULL).decode('utf-8')
        if 'nvidia-container-toolkit' in dpkg_list:
            nvidia_docker_info['installed'] = True

        # Check for NVIDIA runtime in Docker
        docker_info = subprocess.check_output(['docker', 'info', '--format', '{{json .Runtimes}}'], stderr=subprocess.DEVNULL).decode('utf-8')
        runtimes = json.loads(docker_info)
        if 'nvidia' in runtimes:
            nvidia_docker_info['runtime_available'] = True
            nvidia_docker_info['config'] = {"path": runtimes['nvidia']['path']}

        # The following part checks for NVIDIA runtime configuration in daemon.json
        # Keep this if needed, remove if not relevant for your setup
        daemon_json_path = '/etc/docker/daemon.json'
        if os.path.exists(daemon_json_path):
            with open(daemon_json_path, 'r') as f:
                daemon_config = json.load(f)
            if 'runtimes' in daemon_config and 'nvidia' in daemon_config['runtimes']:
                nvidia_docker_info['daemon_config'] = daemon_config['runtimes']['nvidia']
            elif 'default-runtime' in daemon_config and daemon_config['default-runtime'] == 'nvidia':
                nvidia_docker_info['daemon_default'] = True

    except Exception:
        # If any exception occurs, we'll continue with an empty result for Docker
        pass

    return nvidia_docker_info

if __name__ == '__main__':
    run_module()