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
        data |= data.pop('status', {})
        self._data.update(map_values(self.type, data))

    @property
    def data(self):
        return self._data
