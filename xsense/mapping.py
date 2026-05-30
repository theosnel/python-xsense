import typing


def map_bool(value):
    if isinstance(value, bool):
        return value
    return value in (1, '1')


property_mapper = {
    '*': {
        'wifiRssi': 'wifiRSSI'
    },
    'STH0A': {
        'a': 'alarmStatus',
        'b': 'temperature',
        'c': 'humidity',
        'd': 'temperatureUnit',
        'e': 'temperatureRange',
        'f': 'humidityRange',
        'g': 'alarmEnabled',
        'h': 'continuedAlarm',
        't': 'time'
    },
    'STH0B': {
        'a': 'alarmStatus',
        'b': 'temperature',
        'c': 'humidity',
        'd': 'temperatureUnit',
        'e': 'temperatureRange',
        'f': 'humidityRange',
        'g': 'alarmEnabled',
        'h': 'continuedAlarm',
        't': 'time'
    },
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
    },
}

type_mapping = {
    'batInfo': int,
    'rfLevel': int,
    'alarmStatus': map_bool,
    'alarmEnabled': map_bool,
    'muteStatus': map_bool,
    'continuedAlarm': map_bool,
    'coPpm': int,
    'coLevel': int,
    'isLifeEnd': map_bool,
    'isOpen': map_bool,
    'activate': map_bool,
    'temperature': float,
    'humidity': float
}


def map_type(k: str, value: typing.Any):
    return type_mapping[k](value) if k in type_mapping else value


def map_values(device_type: str, data: typing.Dict):
    mapping = property_mapper[device_type] if device_type in property_mapper else {}
    mapping.update(property_mapper.get('*', {}))

    return {
        mapping.get(k, k): map_type(mapping.get(k, k), v)
        for k, v in data.items()
    }
