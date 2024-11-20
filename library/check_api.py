#!/usr/bin/python

from ansible.module_utils.basic import *
import subprocess
import json

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
        cmd = ['curl', '-s', '-m', str(timeout), '-w', '%{http_code}', '-o', '/dev/null', url]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        status_code = result.stdout.strip()

        if status_code == '200':  # Assuming 200 OK means the service is running
            if expected_result is None:
                return {"status": "healthy", "message": f"{api_name} API is running and responded successfully"}
            else:
                # Here we would need to fetch the response body to check for the expected result
                # This is more complex with curl as it would require two separate calls
                body_result = subprocess.run(['curl', '-s', '-m', str(timeout), url], stdout=subprocess.PIPE, text=True, check=True)
                if body_result.stdout.strip() == expected_result:
                    return {"status": "healthy", "message": f"{api_name} API is running and responded as expected"}
                else:
                    return {"status": "unexpected_response", "message": f"{api_name} API did not match expected result: {body_result.stdout.strip()}"}
        else:
            return {"status": "unhealthy", "message": f"{api_name} API responded with status code {status_code}"}

    except subprocess.CalledProcessError as e:
        if 'Connection refused' in str(e.stderr):
            return {"status": "unhealthy", "message": f"{api_name} API not reachable: Connection refused"}
        elif 'timed out' in str(e.stderr):
            return {"status": "unhealthy", "message": f"{api_name} API request timed out"}
        else:
            return {"status": "unhealthy", "message": f"{api_name} API check failed: {e.stderr.strip()}"}

if __name__ == '__main__':
    run_module()