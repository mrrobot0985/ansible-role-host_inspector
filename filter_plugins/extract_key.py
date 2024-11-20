#!/usr/bin/python
# -*- coding: utf-8 -*-

from ansible.errors import AnsibleFilterError

class FilterModule(object):
    def filters(self):
        return {
            'extract_key': self.extract_key
        }

    def extract_key(self, data, key):
        """
        Extracts values for a given key from objects in a list.

        :param data: A dictionary with an 'objects' key containing a list of dictionaries.
        :param key: The key to extract values for.
        :return: A list of values for the specified key from all objects.

        :raises AnsibleFilterError: If the data structure is incorrect or the key is not found.
        """
        try:
            if not isinstance(data, dict) or 'objects' not in data:
                raise AnsibleFilterError("Input must be a dictionary containing an 'objects' key with a list of dictionaries.")

            objects = data.get('objects', [])
            return [obj.get(key) for obj in objects if key in obj]
        except Exception as e:
            raise AnsibleFilterError(f"Error extracting key '{key}': {str(e)}")