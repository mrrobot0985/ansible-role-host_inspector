from collections.abc import Mapping, Iterable

def recursive_merge(dict1, dict2):
    for key, value in dict2.items():
        if key in dict1:
            if isinstance(dict1[key], Mapping) and isinstance(value, Mapping):
                # If both are dicts, merge recursively
                recursive_merge(dict1[key], value)
            elif isinstance(dict1[key], Iterable) and isinstance(value, Iterable) and not isinstance(value, str):
                # If both are lists or other iterables (except strings), extend or concatenate
                if isinstance(dict1[key], list) and isinstance(value, list):
                    # For lists, we extend
                    dict1[key].extend([v for v in value if v not in dict1[key]])
                else:
                    # For sets or other iterables, we union
                    dict1[key] = dict1[key].union(value) if isinstance(dict1[key], set) else list(set(dict1[key]) | set(value))
            else:
                # Overwrite with the new value if types don't match or if neither is a dict or iterable
                dict1[key] = value
        else:
            # If key is not in dict1, simply add it
            dict1[key] = value
    return dict1

class FilterModule(object):
    def filters(self):
        return {
            'merge_dicts': recursive_merge
        }

# from ansible.plugins.filter.core import combine

# def recursive_merge(dict1, dict2):
#     for key, value in dict2.items():
#         if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
#             recursive_merge(dict1[key], value)
#         else:
#             dict1[key] = value
#     return dict1

# class FilterModule(object):
#     def filters(self):
#         return {
#             'merge_dicts': recursive_merge
#         }