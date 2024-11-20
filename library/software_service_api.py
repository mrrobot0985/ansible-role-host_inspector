#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ansible.module_utils.basic import AnsibleModule
import http.client
import json
import os
from urllib.parse import urlparse
import socket
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
            "output_file": f"/tmp/service_check_report_{id}.wav", 
            "tags": ["initiation", "api"]
        })
        id += 1

    # Combine all remediation tasks into one message with tags
    if remediation_tasks:
        actions_text = "Recommended actions are: "
        actions_tags = set()
        for task in remediation_tasks:
            actions_text += f"{task['description']} for {task['tags'][1]} due to {task['reason']}. "
            actions_tags.update(task['tags'])
        
        objects.append({
            "id": str(id),
            "text": actions_text,
            "speaker_id": str(speaker_id),
            "output_file": f"/tmp/service_check_report_{id}.wav",
            "tags": list(actions_tags)
        })
        id += 1

    objects.append({ 
        "id": str(id), 
        "text": "API service check completed.", 
        "speaker_id": str(speaker_id), 
        "output_file": f"/tmp/service_check_report_{id}.wav",
        "tags": ["system", "api", "status"]
    })
    id += 1

    return {
        "next_id": id,
        "objects": objects
    }

def define_remediation(info):
    """Define remediation tasks based on API health checks."""
    remediation_tasks = []
    for api_name, api_info in info.items():
        if api_info['status'] != 'healthy':
            remediation_tasks.append({
                'action': 'check_or_fix_api',
                'description': f"Check or fix {api_name} API",
                'reason': api_info['message'],
                'tags': ['api', api_name]
            })
    return remediation_tasks

def check_api(api_name, base_url, port, endpoint, expected_result, timeout):
    """Check the health of a specific API."""
    parsed_url = urlparse(base_url)
    scheme = parsed_url.scheme.lower()
    host = parsed_url.hostname
    path = f"{parsed_url.path}{endpoint}"
    
    conn = http.client.HTTPSConnection(host, port, timeout=timeout) if scheme == 'https' else http.client.HTTPConnection(host, port, timeout=timeout)
    
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        response_text = response.read().decode('utf-8').strip()

        if response.status >= 200 and response.status < 300:
            if expected_result is None or response_text == expected_result:
                return {"status": "healthy", "message": f"{api_name} API is running and responded as expected"}
            else:
                return {"status": "unexpected_response", "message": f"{api_name} API responded, but not with expected result: {response_text}"}
        else:
            return {"status": "unhealthy", "message": f"{api_name} API responded with HTTP error: {response.status} {response.reason}"}
    except http.client.HTTPException as e:
        logger.error(f"{api_name} API check failed due to HTTP exception: {str(e)}")
        return {"status": "unhealthy", "message": f"{api_name} API check failed due to HTTP exception: {str(e)}"}
    except socket.timeout:
        logger.error(f"{api_name} API request timed out")
        return {"status": "unhealthy", "message": f"{api_name} API request timed out"}
    except Exception as e:
        logger.error(f"{api_name} API check failed: {str(e)}")
        return {"status": "unhealthy", "message": f"{api_name} API check failed: {str(e)}"}
    finally:
        conn.close()

def send_response(module, message, results, id_offset):
    """Generate a uniform response for the module with the given information."""
    logger.info("Sending API status response with facts")
    remediation_tasks = define_remediation(results)
    module.exit_json(
        changed=False,
        msg=message,
        ansible_facts={
            'actions': remediation_tasks,
            'data': {'api_info': results},
            'speech': _set_speech(id_offset, message=message, remediation_tasks=remediation_tasks),
        }
    )

def main():
    """Main function to run the Ansible module."""
    module = AnsibleModule(
        argument_spec=dict(
            apis=dict(type='list', required=True),
            timeout=dict(type='int', default=10),
            id_offset=dict(default=0, type='int', required=False),
            log_path=dict(type='str', required=False)
        ),
        supports_check_mode=True
    )

    id_offset = module.params['id_offset']
    log_path = module.params['log_path']

    global logger
    logger = _setup_logging(log_path)

    logger.info("Starting API service check module execution")
    
    now = datetime.datetime.now()
    epoch = int(now.timestamp())
    message = f"Checking API services."

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

    send_response(module, message, results, id_offset)

if __name__ == '__main__':
    main()