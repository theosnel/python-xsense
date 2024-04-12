from typing import Dict

property_mapper = {
    'STH51': {
        'a': 'alarm_status',
        'b': 'temperature',
        'c': 'humidity',
        'd': 'temperature_unit',
        'e': 'temperature_range',
        'f': 'humidity_range',
        'g': 'alarm_enabled',
        'h': 'continued_alarm',
        't': 'time'
    }
}


def map_values(device_type: str, data: Dict):
    if device_type not in property_mapper:
        return data

    mapping = property_mapper[device_type]
    return {
        mapping.get(k, k): v
        for k, v in data.items()
    }
