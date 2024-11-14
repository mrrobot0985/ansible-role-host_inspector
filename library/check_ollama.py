#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import requests

def run_module():
    module = AnsibleModule(
        argument_spec=dict(
            timeout=dict(type='int', default=5)
        ),
        supports_check_mode=True
    )

    result = dict(
        changed=False,
        ollama_running=False,
        status='',
        message=''
    )

    try:
        response = requests.get('http://127.0.0.1:11434', timeout=module.params['timeout'])
        response.raise_for_status()

        if response.text.strip() == 'Ollama is running':
            result['ollama_running'] = True
            result['status'] = 'running'
            result['message'] = 'Service is running'
        else:
            result['status'] = 'unexpected_response'
            result['message'] = 'Service returned an unexpected response'

    except requests.RequestException:
        result['status'] = 'unreachable'
        result['message'] = 'Service is not reachable'

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()