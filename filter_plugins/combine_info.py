from ansible import errors
from ansible.module_utils._text import to_text
from ansible.module_utils.common.collections import is_sequence, is_iterable

class FilterModule(object):
    def filters(self):
        return {
            'combine_info': self.combine_info,
            'strip_metadata': self.strip_metadata
        }

    def combine_info(self, *args):
        data = {}
        for arg in args:
            if isinstance(arg, dict):
                # Only add relevant keys from each dictionary
                relevant_keys = set(arg.keys()) - {'failed', 'failed_condition', 'skipped', 'skip_reason', 'changed', 'ansible_facts', 'false_condition'}
                data.update({k: arg[k] for k in relevant_keys if not k.startswith('ansible_')})
        return data

    def strip_metadata(self, data):
        if isinstance(data, dict):
            # Keys to remove
            keys_to_remove = ['failed', 'failed_condition', 'skipped', 'skip_reason', 'changed', 'false_condition']
            return {k: self.strip_metadata(v) for k, v in data.items() if k not in keys_to_remove}
        elif isinstance(data, list):
            return[self.strip_metadata(item) for item in data]
        else:
            return data