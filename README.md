Role Name
=========

**host_inspector**

This Ansible role conducts a comprehensive audit of host systems, evaluating aspects like installed applications, system health, network connectivity, security settings, Docker and GPU status, as well as the operational status of critical API services.

Requirements
------------

- **Ansible**: Version 2.1 or higher.
- **Python**: Required on the target hosts for executing Python scripts.
- **Docker**: Required for Docker-related checks.
- **nvidia-smi**: Necessary for NVIDIA GPU status checks.
- **nmap**: Essential for network scanning tasks.
- **Sudo Privileges**: Some checks might need elevated permissions.

Role Variables
--------------

**defaults/main.yml:**

- **apps_to_check**: List of applications to check for installation and version:

  ```yaml
  apps_to_check:
    - curl
    - docker
    - nmap
    - nvidia-smi
    - nvidia-ctk
    - ollama
    - ufw
  ```

- **ollama_check_timeout**: Timeout for checking if the Ollama service is running (default: 10 seconds).

- **scan_timeout**: Timeout for scanning other hosts (default: 60 seconds).

- **scan_ports**: Ports to be scanned by nmap (default: `'22,80,443'`).

- **apis_to_test**: List of APIs to test:

```yaml
apis_to_test:
  - name: "ollama"
    url: "http://127.0.0.1"
    port: 11434
    endpoint: "/"
    expected_result: "Ollama is running"
  - name: "prometheus"
    port: 9090
    endpoint: "/-/healthy"
  - name: "grafana"
    port: 3000
    endpoint: "/api/health"
```

- **api_test_timeout**: Timeout for API tests (default: 10 seconds).

These can be adjusted in the playbook or inventory file to suit specific needs.

Dependencies
------------

While there are no explicit role dependencies, ensure all required system tools and Python libraries are installed on the hosts.

Example Playbook
----------------

Usage example:

```yaml
- hosts: all
  roles:
    - role: mrrobot0985.host_inspector
      vars:
        debug: true
        apps_to_check:
          - curl
          - docker
          - nmap
        scan_ports: '22,80,443,3000'
        apis_to_test:
          - name: "grafana"
            port: 3001
            endpoint: "/api/health"
  tasks:
    - name: Display host inspection results
      debug:
        var: host_inspector
      when: debug is defined and debug
```

License
-------

**The-Unlicense**

Author Information
------------------

For inquiries or issues related to `host_inspector`, please contact:

- **Author**: Mister Robot  
- **Company**: BrainXio

More information or to report issues, visit the GitHub repository for this role.