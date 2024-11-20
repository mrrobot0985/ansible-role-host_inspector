# File: lookup_plugins/obfuscate.py

import re
from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        if not isinstance(terms, list):
            terms = [terms]

        def obfuscate_value(value, key=None):
            if isinstance(value, str):
                # Obfuscate GPU UUID
                value = re.sub(r'(GPU-)([a-zA-Z0-9-]+)', r'\1XXXXXX', value)
                # Obfuscate username or user key
                if key and key.lower() in ['username', 'user', 'hostname', 'user_id']:
                    value = '[OBFUSCATED]'
                # Obfuscate WAN address
                elif key == 'wan_address':
                    value = '[OBFUSCATED]'
                # Obfuscate paths
                elif key == 'path':
                    value = re.sub(r'/home/[^/]+', r'/home/[OBFUSCATED]', value)
            elif isinstance(value, dict):
                value = {k: obfuscate_value(v, k) for k, v in value.items()}
            elif isinstance(value, list):
                value = [obfuscate_value(item) for item in value]
            return value

        results = []
        for term in terms:
            if isinstance(term, dict):
                results.append(obfuscate_value(term))
            else:
                results.append(term)  # If not dict or list, just append as is

        return results