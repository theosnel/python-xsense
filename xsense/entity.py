from xsense.mapping import map_values


class Entity:
    online = None
    type = None
    _data = None

    def __init__(
            self,
            **kwargs
    ):
        self.room_id = kwargs.get('roomId')
        self._data = {}

    def set_data(self, values: dict):
        data = values.copy()
        if 'online' in values:
            self.online = values.pop('online') != '0'
        if values.get('onlineTime'):
            self.online = True
        data |= data.pop('status', {})
        # sofware versions are reported differently per device
        if 'swMain' in data:
            data['network_sw'] = data.get('sw')
            data['sw'] = data.pop('swMain', None)
        self._data.update(map_values(self.type, data))

    @property
    def data(self):
        return self._data

    @property
    def shadow_name(self):
        return f'{self.type}{self.sn}'
