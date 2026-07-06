from datetime import datetime, timedelta, timezone

from xsense.base import XSenseBase
from xsense.device import Device
from xsense.entity import Entity
from xsense.entity_map import EntityType
from xsense.house import House
from xsense.station import Station


class FakeSigner:
    def presign_url(self, *args):
        return "wss://mqtt.example/mqtt?sig=abc"


def _house():
    house = House(FakeSigner(), "house-id", "Home", "US", "us-east-1", "mqtt.example")
    house.set_rooms(
        {
            "houseRooms": {"room-1": {"roomName": "Kitchen"}},
            "roomSort": ["room-1"],
        }
    )
    return house


def test_entity_online_state_uses_explicit_flag_and_report_time():
    entity = Entity(onLine=1)
    entity.type = "XS01-WX"

    entity.set_data({"online": 0})

    assert entity.online is False

    utc_time = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    entity.set_data({"utcTime": utc_time, "onlineTime": utc_time})

    assert entity.online is True


def test_shadow_name_follows_app_thing_name_rules():
    station = Station(_house(), stationId="sbs", stationSn="BASE123", category="SBS10")
    assert station.shadow_name == "BASE123"

    wifi_station = Station(
        _house(), stationId="wx", stationSn="ST123", category="SC07-WX"
    )
    assert wifi_station.shadow_name == "SC07-WX-ST123"

    smoke_station = Station(
        _house(), stationId="smoke", stationSn="EN123", category="XS01-WX"
    )
    assert smoke_station.shadow_name == "XS01-WX-EN123"

    child = Device(
        station,
        deviceId="child",
        deviceSn="CHILD123",
        deviceType="STH0B",
        deviceName="Thermo",
    )
    assert child.shadow_name == "SBS50BASE123"


def test_house_set_stations_maps_app_camera_list():
    house = _house()

    house.set_stations(
        {
            "stationSort": [],
            "stations": [],
            "cameras": [
                {
                    "ipcId": "cam-id",
                    "ipcSn": "CAM123",
                    "ipcName": "Front",
                    "category": "SSC0A",
                    "roomId": "room-1",
                    "userId": "user-id",
                    "userName": "User",
                }
            ],
        }
    )

    camera = house.stations["cam-id"]
    assert camera.sn == "CAM123"
    assert camera.name == "Front"
    assert camera.type == "SSC0A"
    assert camera.entity_type == EntityType.CAMERA
    assert camera.online is True


def test_station_and_device_construction_accept_identity_aliases():
    house = _house()

    station = Station(
        house,
        stationSN="BASE123",
        stationName="Base",
        deviceType="SBS50",
    )
    device = Device(
        station,
        deviceId="device-id",
        devSerialNumber="DEV123",
        category="XS01-M",
        deviceName="Smoke",
    )

    assert station.sn == "BASE123"
    assert station.type == "SBS50"
    assert device.sn == "DEV123"
    assert device.type == "XS01-M"


def test_station_set_devices_adds_room_and_group_light_devices():
    house = _house()
    station = Station(
        house,
        stationId="station-id",
        stationSn="SBS50123",
        stationName="Base",
        category="SBS50",
        roomId="room-1",
    )

    station.set_devices(
        {
            "roomId": "room-1",
            "devices": [
                {
                    "deviceId": "light-1",
                    "deviceSn": "LIGHT001",
                    "deviceType": "LP/N-SA-0B",
                    "deviceName": "Light",
                    "roomId": "room-1",
                    "groupId": 12,
                    "online": 1,
                    "on": "1",
                }
            ],
            "groupList": [
                {"groupId": 12, "groupName": "All Lights", "createTime": "171"}
            ],
        }
    )

    light = station.get_device_by_sn("LIGHT001")
    group = station.get_group_device(12)

    assert light.data["roomName"] == "Kitchen"
    assert group is not None
    assert group.type == "group-L"
    assert group.data["on"] is True
    assert group.data["devs"] == ["LIGHT001"]


def test_station_set_devices_canonicalizes_child_identity_aliases():
    station = Station(
        _house(),
        stationId="station-id",
        stationSn="BASE123",
        stationName="Base",
        category="SBS50",
    )

    station.set_devices(
        {
            "devices": [
                {
                    "devSerialNumber": 12345,
                    "category": "XS01-M",
                    "deviceName": "Smoke",
                },
                {
                    "deviceId": "",
                    "deviceName": "Malformed",
                },
                {
                    "deviceSn": "NO-ID123",
                    "deviceType": "SDS0A",
                    "deviceName": "Door",
                },
            ]
        }
    )

    smoke = station.get_device_by_sn("12345")
    door = station.get_device_by_sn("NO-ID123")

    assert smoke is not None
    assert smoke.sn == "12345"
    assert smoke.type == "XS01-M"
    assert door is not None
    assert station.get_device_by_sn(12345) is smoke
    assert len(station.devices) == 2


def test_parse_get_state_routes_child_shadow_payloads():
    house = _house()
    station = Station(
        house,
        stationId="station-id",
        stationSn="SBS50123",
        stationName="Base",
        category="SBS50",
    )
    station.set_devices(
        {
            "devices": [
                {
                    "deviceId": "device-id",
                    "deviceSn": "DEV123",
                    "deviceType": "STH0B",
                    "deviceName": "Thermo",
                }
            ]
        }
    )

    XSenseBase().parse_get_state(
        station,
        {
            "activate": "1",
            "devs": {
                "DEV123": {
                    "temperature": "20.5",
                    "humidity": "44",
                    "online": "1",
                }
            },
        },
    )

    device = station.get_device_by_sn("DEV123")
    assert station.has_alarm is True
    assert device.online is True
    assert device.data["temperature"] == 20.5
    assert device.data["humidity"] == 44.0


def test_parse_get_state_routes_child_shadow_payload_identity_aliases():
    station = Station(
        _house(),
        stationId="station-id",
        stationSn="BASE123",
        stationName="Base",
        category="SBS50",
    )
    station.set_devices(
        {
            "devices": [
                {
                    "deviceId": "device-id",
                    "deviceSn": "DEV123",
                    "deviceType": "XS01-M",
                    "deviceName": "Smoke",
                }
            ]
        }
    )

    for alias in ("devSerialNumber", "serialNumber", "sn"):
        XSenseBase().parse_get_state(
            station,
            {
                "devs": [
                    {
                        alias: "DEV123",
                        "online": "1",
                        "temperature": "21.5",
                    }
                ]
            },
        )

    device = station.get_device_by_sn("DEV123")
    assert device.online is True
    assert device.data["temperature"] == 21.5


def test_sbs10_door_child_shadow_payload_sets_open_state():
    house = _house()
    station = Station(
        house,
        stationId="station-id",
        stationSn="BASE123",
        stationName="Base",
        category="SBS10",
    )
    station.set_devices(
        {
            "devices": [
                {
                    "deviceId": "door-id",
                    "deviceSn": "DOOR123",
                    "deviceType": "SDS0A",
                    "deviceName": "Door",
                }
            ]
        }
    )

    XSenseBase().parse_get_state(
        station,
        {
            "devs": {
                "DOOR123": {
                    "status": "open",
                    "online": "1",
                }
            }
        },
    )

    door = station.get_device_by_sn("DOOR123")
    assert door.online is True
    assert door.entity_type == EntityType.DOOR
    assert door.data["isOpen"] is True


def test_door_status_aliases_normalize_to_is_open():
    house = _house()
    station = Station(
        house,
        stationId="station-id",
        stationSn="BASE123",
        stationName="Base",
        category="SBS10",
    )
    device = Device(
        station,
        deviceId="door-id",
        deviceSn="DOOR123",
        deviceType="SES01",
        deviceName="Door",
    )

    device.set_data({"a": "closed"})
    assert device.data["isOpen"] is False

    device.set_data({"doorStatus": "open"})
    assert device.data["isOpen"] is True


def test_security_line_fields_from_issue_29_are_normalized():
    house = _house()
    station = Station(
        house,
        stationId="station-id",
        stationSn="BASE123",
        stationName="Base",
        category="SBS50",
    )
    station.set_devices(
        {
            "devices": [
                {
                    "deviceId": "door-id",
                    "deviceSn": "DOOR123",
                    "deviceType": "SDS0A",
                    "deviceName": "Door",
                }
            ]
        }
    )

    XSenseBase().parse_get_state(
        station,
        {
            "devs": {
                "DOOR123": {
                    "isOpen": "1",
                    "openRemind": "1",
                    "online": "1",
                    "batInfo": "3",
                    "rfLevel": "2",
                    "alarmStatus": "0",
                }
            }
        },
    )

    door = station.get_device_by_sn("DOOR123")
    assert door.data["isOpen"] is True
    assert door.data["openRemind"] is True
    assert door.online is True
    assert door.data["batInfo"] == 3
    assert door.data["rfLevel"] == 2
    assert door.data["alarmStatus"] is False


def test_parse_get_state_updates_group_light_from_shadow_payload():
    house = _house()
    station = Station(
        house,
        stationId="station-id",
        stationSn="SBS50123",
        stationName="Base",
        category="SBS50",
    )
    station.set_devices(
        {
            "devices": [],
            "groupList": [{"groupId": 5, "groupName": "Hall", "createTime": "171"}],
        }
    )

    XSenseBase().parse_get_state(
        station,
        {
            "groupId": 5,
            "isOn": "1",
            "devs": [{"deviceSn": "A"}, {"deviceSn": "B"}],
        },
    )

    group = station.get_group_device(5)
    assert group.data["on"] is True
    assert group.data["devs"] == [{"deviceSn": "A"}, {"deviceSn": "B"}]


def test_apply_safe_mode_updates_station_attribute_and_data():
    station = Station(
        _house(),
        stationId="station-id",
        stationSn="SBS50123",
        stationName="Base",
        category="SBS50",
    )

    XSenseBase().apply_safe_mode(station, "home")

    assert station.safe_mode == "home"
    assert station.data["safeMode"] == "home"


def test_parse_get_state_keeps_safe_mode_in_sync_with_other_fields():
    station = Station(
        _house(),
        stationId="station-id",
        stationSn="SBS50123",
        stationName="Base",
        category="SBS50",
    )

    XSenseBase().parse_get_state(station, {"safeMode": "away", "alarmStatus": "1"})

    assert station.safe_mode == "away"
    assert station.data["safeMode"] == "away"
    assert station.data["alarmStatus"] is True
    assert station.alarm_mode == "away"
    assert station.is_armed is True


def test_parse_get_state_normalizes_apk_is_alarm_to_alarm_status():
    station = Station(
        _house(),
        stationId="station-id",
        stationSn="SBS50123",
        stationName="Base",
        category="SBS50",
    )
    station.set_devices(
        {
            "devices": [
                {
                    "deviceId": "device-id",
                    "deviceSn": "DEV123",
                    "deviceType": "SWS51",
                    "deviceName": "Water",
                }
            ]
        }
    )

    XSenseBase().parse_get_state(
        station,
        {
            "isAlarm": "1",
            "devs": {
                "DEV123": {
                    "isAlarm": "0",
                }
            },
        },
    )

    device = station.get_device_by_sn("DEV123")
    assert station.data["alarmStatus"] is True
    assert station.has_alarm is True
    assert device.data["alarmStatus"] is False


def test_xs01_m_alias_alarm_payload_updates_child_alarm_status():
    station = Station(
        _house(),
        stationId="station-id",
        stationSn="BASE123",
        stationName="Base",
        category="SBS50",
    )
    station.set_devices(
        {
            "devices": [
                {
                    "deviceId": "smoke-id",
                    "deviceSn": "SMOKE123",
                    "deviceType": "XS01-M",
                    "deviceName": "Smoke",
                }
            ]
        }
    )

    XSenseBase().parse_get_state(
        station,
        {
            "devs": [
                {
                    "devSerialNumber": "SMOKE123",
                    "isAlarm": "1",
                }
            ]
        },
    )

    smoke = station.get_device_by_sn("SMOKE123")
    assert smoke.data["alarmStatus"] is True


def test_xc0m_ir_compact_fields_and_range_strings_are_normalized():
    station = Station(
        _house(),
        stationId="station-id",
        stationSn="BASE123",
        stationName="Base",
        category="SBS10",
    )
    device = Device(
        station,
        deviceId="device-id",
        deviceSn="DEV123",
        deviceType="XC0M-iR",
        deviceName="Combo",
    )

    device.set_data({"a": "1", "b": "20.5", "c": "45", "e": "10,30", "f": "40,60"})

    assert device.data["alarmStatus"] is True
    assert device.data["temperature"] == 20.5
    assert device.data["humidity"] == 45.0
    assert device.data["tRange"] == [10.0, 30.0]
    assert device.data["hRange"] == [40.0, 60.0]


def test_station_alarm_mode_uses_alarm_data_before_safe_mode():
    station = Station(
        _house(),
        stationId="station-id",
        stationSn="SBS50123",
        stationName="Base",
        category="SBS50",
        safeMode="home",
    )

    assert station.alarm_mode == "home"
    assert station.is_armed is True

    station.set_alarm_data({"mode": "disarmed", "safeMode": "away"})

    assert station.alarm_mode == "disarmed"
    assert station.is_armed is False


def test_station_lookup_helpers_find_station_by_serial_shadow_and_child_device():
    house = _house()
    station = Station(
        house,
        stationId="station-id",
        stationSn="BASE123",
        stationName="Base",
        category="SBS50",
    )
    station.set_devices(
        {
            "devices": [
                {
                    "deviceId": "device-id",
                    "deviceSn": "DEV123",
                    "deviceType": "STH0B",
                    "deviceName": "Thermo",
                }
            ]
        }
    )
    house.stations[station.entity_id] = station
    client = XSenseBase()
    client.houses = {house.house_id: house}

    assert client.station_by_sn("BASE123") is station
    assert client.station_by_shadow_name("SBS50BASE123") is station
    assert client.station_by_device_sn("DEV123") is station
    assert client.station_by_device_sn("BASE123") is station
    assert client.station_by_sn("missing") is None
    assert client.station_by_shadow_name(None) is None
    assert client.station_by_device_sn("") is None


def test_action_support_requires_resolvable_route():
    house = _house()
    station = Station(
        house,
        stationId="station-id",
        stationSn="ST123",
        stationName="Base",
        category="SBS50",
    )
    device = Device(
        station,
        deviceId="device-id",
        deviceSn="DEV123",
        deviceType="SC07-MR",
        deviceName="Smoke",
    )
    client = XSenseBase()

    assert client.has_action(device, "test")
    assert client.action_definition(device, "test") is not None

    device.sn = None

    assert not client.has_action(device, "test")
