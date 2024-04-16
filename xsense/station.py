from typing import List, Dict

from xsense.device import Device
from xsense.entity import Entity


class Station(Entity):
    devices: Dict[str, Device]
    device_order: List[str]
    device_by_sn: Dict[str, str]

    def __init__(
            self,
            parent,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.house = parent
        self.safe_mode = kwargs.get('safeMode')
        self.entity_id = kwargs.get('stationId')
        self.name = kwargs.get('stationName')
        self.sn = kwargs.get('stationSn')
        self.online = kwargs.get('onLine')
        self.type = kwargs.get('category')

    def set_devices(self, data):
        self.device_order = data.get('deviceSort')
        result = {}
        result_sn = {}
        for i in data.get('devices'):
            d = Device(
                self,
                **i
            )
            result[i['deviceId']] = d
            result_sn[i['deviceSn']] = i['deviceId']
        self.devices = result
        self.device_by_sn = result_sn

    def get_device_by_sn(self, sn: str):
        if device_id := self.device_by_sn.get(sn):
            return self.devices.get(device_id)
        return None
