from xsense.mapping import map_values


class Device:
    online = None
    type = None
    _status = None

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

        self._status = {}

    def set_status(self, values: dict):
        data = values.copy()
        self.online = values.pop('online', False)
        self.type = values.pop('type', '')
        data |= data.pop('status', {})
        self._status = map_values(self.type, data)

    @property
    def status(self):
        return self._status
