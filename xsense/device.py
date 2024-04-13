from xsense.mapping import map_values


class Device:
    online = None
    type = None
    _data = None

    def __init__(
            self,
            station,
            device_id,
            name,
            sn,
            device_type,
            room_id
    ):
        self.station = station
        self.device_id = device_id
        self.name = name
        self.sn = sn
        self.device_type = device_type
        self.room_id = room_id

        self._data = {}

    def set_data(self, values: dict):
        data = values.copy()
        self.online = values.pop('online', False)
        self.type = values.pop('type', '')
        data |= data.pop('status', {})
        self._data = map_values(self.type, data)

    @property
    def data(self):
        return self._data
