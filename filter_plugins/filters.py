import re
import json
import xml.etree.ElementTree as ET

def to_nice_xml(value):
    def dict_to_xml(tag, d):
        elem = ET.Element(tag)
        for key, val in d.items():
            child = ET.Element(key)
            if isinstance(val, dict):
                child = dict_to_xml(key, val)
            else:
                child.text = str(val)
            elem.append(child)
        return elem

    if isinstance(value, dict):
        root = dict_to_xml('root', value)
        return ET.tostring(root, encoding='unicode', method='xml')
    return str(value)

class FilterModule(object):
    def filters(self):
        return {
            'to_nice_xml': to_nice_xml,
        }
