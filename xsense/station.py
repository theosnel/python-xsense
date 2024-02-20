from typing import List, Dict

from xsense.device import Device


class Station:
    devices: Dict[str, Dict[str, Device]]
    device_order: List[str]
    device_by_sn: Dict[str, str]

    def __init__(
            self,
            parent,
            station_id,
            station_name,
            station_sn,
            category,
            sw,
            safe_mode,
            online
    ):
        self.house = parent
        self.station_id = station_id
        self.name = station_name
        self.sn = station_sn
        self.category = category
        self.sw = sw
        self.safe_mode = safe_mode
        self.online = online

    def set_devices(self, data):
        self.device_order = data.get('deviceSort')
        result = {}
        result_sn = {}
        for i in data.get('devices'):
            d = Device(
                self,
                i['deviceId'],
                i['deviceName'],
                i['deviceSn'],
                i['deviceType'],
                i['roomId']
            )
            result[i['deviceId']] = d
            result_sn[i['deviceSn']] = i['deviceId']
        self.devices = result
        self.device_by_sn = result_sn

    def get_device_by_sn(self, sn: str):
        if device_id := self.device_by_sn.get(sn):
            return self.devices.get(device_id)
        return None
