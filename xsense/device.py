from xsense.entity import Entity


class Device(Entity):
    def __init__(
            self,
            station,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.station = station
        self.entity_id = kwargs.get('deviceId')
        self.type = kwargs.get('deviceType')
        self.name = kwargs.get('deviceName')
        self.sn = kwargs.get('deviceSn')
