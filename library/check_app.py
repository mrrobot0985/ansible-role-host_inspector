#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
import os
import subprocess

def run_module():
    module = AnsibleModule(
        argument_spec=dict(
            apps=dict(type='list', required=True),
            # Optionally you could add other parameters here to control how we check for apps
        ),
        supports_check_mode=True
    )

    app_info = {}

    for app in module.params['apps']:
        app_info[app] = check_app_installed(app)

    result = dict(
        changed=False,
        app_info=app_info
    )

    module.exit_json(**result)

def check_app_installed(app_name):
    # This function checks if the app is installed. 
    # Note: This is a basic check and might need to be adapted for different OS types.
    
    # For Debian-based systems (Ubuntu, Debian)
    if os.path.exists("/usr/bin/dpkg-query"):
        try:
            cmd = ["dpkg-query", "-W", "-f='${Status}'", app_name]
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            # If output contains "ok installed" then the package is installed
            return "installed" in result.stdout
        except subprocess.CalledProcessError:
            return False

    # For RedHat-based systems (CentOS, Fedora)
    elif os.path.exists("/usr/bin/rpm"):
        try:
            cmd = ["rpm", "-q", app_name]
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            # If the command returns without error, the package is assumed to be installed
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False

    # For macOS
    elif os.path.exists("/usr/bin/pkgutil"):
        try:
            cmd = ["pkgutil", "--pkg-info", app_name]
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False

    # For Windows, you would need to implement checks for MSI or other package managers
    # This is beyond the scope here but could include checking registry or wmic commands

    # If none of the above match, we can't check for this app or it's not in a known package manager
    return "Unknown"

if __name__ == '__main__':
    run_module()