import typing

property_mapper = {
    'STH51': {
        'a': 'alarmStatus',
        'b': 'temperature',
        'c': 'humidity',
        'd': 'temperatureUnit',
        'e': 'temperatureRange',
        'f': 'humidityRange',
        'g': 'alarmEnabled',
        'h': 'continuedAlarm',
        't': 'time'
    }
}

type_mapping = {
    'batInfo': int,
    'rfLevel': int,
    'alarmStatus': lambda x: x == '1',
    'alarmEnabled': lambda x: x == '1',
    'muteStatus': lambda x: x == '1',
    'continuedAlarm': lambda x: x == '1',
    'coPpm': int,
    'coLevel': int,
    'isLifeEnd': lambda x: x == '1',
    'temperature': float,
    'humidity': float
}


def map_type(k: str, value: typing.Any):
    return type_mapping[k](value) if k in type_mapping else value


def map_values(device_type: str, data: typing.Dict):
    mapping = property_mapper[device_type] if device_type in property_mapper else {}

    return {
        mapping.get(k, k): map_type(mapping.get(k, k), v)
        for k, v in data.items()
    }
