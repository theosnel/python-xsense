from typing import List, Dict

from xsense.station import Station


class House:
    rooms = Dict[str, Dict[str, str]]
    room_order = List[str]

    stations = List[Dict[str, str]]
    station_order = List[str]

    def __init__(
            self,
            house_id: str,
            name: str,
            region: str,
            mqtt_region: str,
            mqtt_server: str
    ):
        self.house_id = house_id
        self.name = name
        self.region = region
        self.mqtt_region = mqtt_region
        self.mqtt_server = mqtt_server

    def set_rooms(self, data):
        self.rooms = data.get('houseRooms')
        self.room_order = data.get('roomSort')

    def set_stations(self, data):
        self.station_order = data.get('stationSort')

        stations = {}
        for i in data.get('stations', []):
            s = Station(
                self,
                **i
            )
            s.set_devices(i)

            stations[i['stationId']] = s

        self.stations = stations
