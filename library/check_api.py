#!/usr/bin/python
from ansible.module_utils.basic import *
import requests
from requests.exceptions import RequestException

def run_module():
    module = AnsibleModule(
        argument_spec=dict(
            apis=dict(type='list', required=True),
            timeout=dict(type='int', default=10),
        ),
        supports_check_mode=True
    )

    results = {}
    for api_config in module.params['apis']:
        api_name = api_config.get('name')
        results[api_name] = check_api(
            api_name,
            api_config.get('url', 'http://localhost'),
            api_config.get('port', 80),
            api_config.get('endpoint', '/'),
            api_config.get('expected_result', None),
            module.params['timeout']
        )

    module.exit_json(changed=False, api_info=results)

def check_api(api_name, base_url, port, endpoint, expected_result, timeout):
    url = f"{base_url}:{port}{endpoint}"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        
        if expected_result is None or response.text.strip() == expected_result:
            return {"status": "healthy", "message": f"{api_name} API is running and responded as expected"}
        else:
            return {"status": "unexpected_response", "message": f"{api_name} API responded, but not with expected result: {response.text.strip()}"}
    
    except requests.exceptions.ConnectionError:
        return {"status": "unhealthy", "message": f"{api_name} API not reachable: Connection refused"}
    except requests.exceptions.Timeout:
        return {"status": "unhealthy", "message": f"{api_name} API request timed out"}
    except requests.exceptions.HTTPError as e:
        return {"status": "unhealthy", "message": f"{api_name} API responded with HTTP error: {e.response.status_code}"}
    except RequestException as e:
        return {"status": "unhealthy", "message": f"{api_name} API check failed: {str(e)}"}

if __name__ == '__main__':
    run_module()