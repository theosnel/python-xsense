class Device:
    bat_info = None
    online = None
    rf_level = None
    status = None
    _values = None

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

        self._values = {}

    def set_status(self, bat_info, online, rf_level, status):
        self.bat_info = bat_info
        self.online = online
        self.rf_level = rf_level
        self.status = status

    def set_value(self, key, value):
        self._values[key] = value

    def set_values(self, values):
        self._values = values

    @property
    def data(self):
        return self._values
