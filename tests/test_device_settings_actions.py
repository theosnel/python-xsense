import asyncio
from types import SimpleNamespace

from xsense.async_xsense import (
    AsyncXSense,
    comfort_pair,
    light_group_list,
    light_schedule_list,
    non_empty_strings,
    schedule_time,
    schedule_week_days,
    typed_option,
)
from xsense.device import Device
from xsense.entity_map import EntityType
from xsense.exceptions import XSenseError
from xsense.house import House
from xsense.station import Station


class RecordingClient(AsyncXSense):
    def __init__(self):
        super().__init__(session=None)
        self.userid = "user-id"
        self.do_thing_calls = []
        self.api_calls = []

    async def do_thing(self, station, page, data):
        self.do_thing_calls.append((station, page, data))
        return {"ok": True}

    async def api_call(self, code, unauth=False, **kwargs):
        self.api_calls.append((code, kwargs))
        if code == "405105":
            return {"schedList": [{"schedId": "sched-1"}]}
        if code == "405001":
            return {"reData": {"groupList": [{"groupId": "group-1"}]}}
        return {"ok": True}


class FakeEntity:
    def __init__(self, *, station=None, entity_type=None, entity_id="entity-id"):
        self.station = station
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.sn = "DEV123"
        self.type = "STH0B"
        self.data = {}

    @property
    def shadow_name(self):
        return f"{self.type}{self.sn}"

    def set_data(self, values):
        self.data.update(values)


def _station(station_type="SBS50"):
    station = SimpleNamespace()
    station.entity_id = "station-id"
    station.sn = "BASE123"
    station.type = station_type
    station.data = {}
    station.station = station
    station.entity_type = EntityType.BASESTATION
    station.shadow_name = f"{station_type}{station.sn}"
    return station


def test_station_shadow_setting_uses_app_payload_shape():
    station = _station("SBS10")
    station.data = {"voiceVol": 4, "alarmTone": 2}
    client = RecordingClient()

    asyncio.run(client.update_shadow_setting(station, "alarmVol", 7))

    target, topic, payload = client.do_thing_calls[0]
    desired = payload["state"]["desired"]
    assert target is station
    assert topic == "info_BASE123"
    assert desired == {
        "shadow": "infoBase",
        "alarmVol": "7",
        "stationSN": "BASE123",
        "voiceVol": "4",
        "alarmTone": "2",
    }


def test_temperature_shadow_setting_includes_station_and_change_unit():
    station = _station("SBS50")
    device = FakeEntity(station=station, entity_type=EntityType.TEMPERATURE)
    client = RecordingClient()

    asyncio.run(client.update_shadow_setting(device, "tempUnit", "C"))

    target, topic, payload = client.do_thing_calls[0]
    desired = payload["state"]["desired"]
    assert target is station
    assert topic == "2nd_cfg_DEV123"
    assert desired == {
        "shadow": "infoDev",
        "tempUnit": "C",
        "deviceSN": "DEV123",
        "stationSN": "BASE123",
        "changeUnit": "1",
    }


def test_light_power_and_scene_use_app_shadow_payloads():
    station = _station("SBS50")
    light = FakeEntity(station=station, entity_type=EntityType.LIGHT)
    light.sn = "LIGHT123"
    client = RecordingClient()

    asyncio.run(client.update_light_power(light, True))
    asyncio.run(client.update_light_scene(light, "2"))

    _, power_topic, power_payload = client.do_thing_calls[0]
    power = power_payload["state"]["desired"]
    assert power_topic == "2nd_lamppower"
    assert power["isOn"] == "1"
    assert power["dev"] == "LIGHT123"
    assert power["shadow"] == "lampPower"
    assert power["stationSN"] == "BASE123"
    assert power["userId"] == "user-id"

    _, scene_topic, scene_payload = client.do_thing_calls[1]
    scene = scene_payload["state"]["desired"]
    assert scene_topic == "2nd_cfg_LIGHT123"
    assert scene == {
        "shadow": "infoDev",
        "deviceSN": "LIGHT123",
        "lightScene": "2",
        "onEvent": "1",
        "pirEnable": "0",
        "awaitEnable": "1",
    }


def test_group_light_power_uses_group_payload_shape():
    station = _station("SBS50")
    group = FakeEntity(station=station, entity_type=EntityType.LIGHT)
    group.type = "group-L"
    group.data = {"groupId": 12, "devs": ["LIGHT1", "LIGHT2"]}
    client = RecordingClient()

    asyncio.run(client.update_light_power(group, False))

    _, topic, payload = client.do_thing_calls[0]
    desired = payload["state"]["desired"]
    assert topic == "2nd_grouppower"
    assert desired["isOn"] == "0"
    assert desired["groupId"] == 12
    assert desired["devs"] == ["LIGHT1", "LIGHT2"]
    assert desired["shadow"] == "groupLampPower"
    assert desired["stationSN"] == "BASE123"
    assert desired["timeOut"] == "180"


def test_light_schedule_and_group_apis_use_app_biz_codes():
    station = _station("SBS50")
    light = FakeEntity(station=station, entity_type=EntityType.LIGHT)
    light.entity_id = "light-id"
    client = RecordingClient()

    schedules = asyncio.run(client.query_light_schedules(light))
    asyncio.run(
        client.create_light_schedule(
            light,
            name="Evening",
            start_time="18:00",
            end_time="23:00",
            week_days=["1", "2"],
            enabled=True,
            time_zone="America/St_Johns",
        )
    )
    groups = asyncio.run(client.query_light_groups(light))
    asyncio.run(client.bind_light_group(light, name="Hall", device_ids=["light-id"]))

    assert schedules == [{"schedId": "sched-1"}]
    assert groups == [{"groupId": "group-1"}]
    assert client.api_calls[0] == (
        "405105",
        {"stationId": "station-id", "deviceId": "light-id"},
    )
    assert client.api_calls[1] == (
        "405101",
        {
            "stationId": "station-id",
            "schedName": "Evening",
            "deviceIds": ["light-id"],
            "timeZone": "America/St_Johns",
            "startTime": "1800",
            "endTime": "2300",
            "isEnable": "1",
            "weekDays": ["1", "2"],
            "newTimeZoneMode": "1",
        },
    )
    assert client.api_calls[2] == ("405001", {"stationId": "station-id"})
    assert client.api_calls[3] == (
        "405005",
        {"stationId": "station-id", "groupName": "Hall", "deviceIds": ["light-id"]},
    )


def test_light_schedule_and_group_normalizers():
    assert schedule_time("7:05") == "0705"
    assert schedule_time("2300") == "2300"
    assert schedule_week_days([" 1 ", 7]) == ["1", "7"]
    assert light_schedule_list({"schedule": [1]}) == [1]
    assert light_schedule_list([2]) == [2]
    assert light_group_list({"reData": {"groupList": [3]}}) == [3]
    assert light_group_list({"groups": [4]}) == [4]
    assert non_empty_strings([" one ", "", "two"], "ids") == ["one", "two"]
    assert typed_option("2") == 2
    assert typed_option("eco") == "eco"
    assert comfort_pair(["20", 26], [1.0, 2.0]) == [20.0, 26.0]
    assert comfort_pair(["bad"], [1.0, 2.0]) == [1.0, 2.0]


def test_light_schedule_and_group_normalizers_reject_invalid_values():
    for value in ("24:00", "2360", "bad"):
        try:
            schedule_time(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{value!r} should fail schedule time validation")

    try:
        schedule_week_days(["0"])
    except ValueError:
        pass
    else:
        raise AssertionError("weekday 0 should fail validation")

    try:
        non_empty_strings(["", " "], "ids")
    except ValueError:
        pass
    else:
        raise AssertionError("empty id list should fail validation")


def test_co_pre_alarm_and_array_settings_use_app_payloads():
    station = _station("SBS50")
    device = FakeEntity(station=station, entity_type=EntityType.CO)
    client = RecordingClient()

    asyncio.run(client.update_co_pre_alarm(device, enabled=True, period=30))
    asyncio.run(
        client.update_shadow_array_setting(
            device, "tComfort", [18.0, 24.0], comfort_type="temp"
        )
    )

    _, warn_topic, warn_payload = client.do_thing_calls[0]
    warn = warn_payload["state"]["desired"]
    assert warn_topic == "2nd_warnperiod"
    assert warn["shadow"] == "appWarnPerion"
    assert warn["deviceSN"] == "DEV123"
    assert warn["stationSN"] == "BASE123"
    assert warn["userId"] == "user-id"
    assert warn["warnIsOpen"] == "1"
    assert warn["warnPeriod"] == "30"

    _, settings_topic, settings_payload = client.do_thing_calls[1]
    settings = settings_payload["state"]["desired"]
    assert settings_topic == "2nd_cfg_DEV123"
    assert settings == {
        "shadow": "infoDev",
        "deviceSN": "DEV123",
        "stationSN": "BASE123",
        "tComfort": [18.0, 24.0],
        "comfortType": "temp",
    }


def test_apk_control_compatibility_methods_use_expected_topics_and_payloads():
    station = _station("SBS50")
    device = FakeEntity(station=station, entity_type=EntityType.MOTION)
    device.type = "SMS0A"
    client = RecordingClient()

    asyncio.run(client.set_station_mode(station, "away", force_arm="1"))
    asyncio.run(client.trigger_sos(station, "2"))
    asyncio.run(client.cancel_sos(station))
    asyncio.run(client.cancel_alarm(station))
    asyncio.run(client.set_sos_sound(station, "3"))
    asyncio.run(client.activate_device(device))
    asyncio.run(client.set_install_guide_test(device, detc_sens="2"))
    asyncio.run(client.signal_test(device, test_time="9"))
    asyncio.run(client.set_motion_test(device, active=False))
    asyncio.run(client.mute_driveway(device, mute=True))

    calls = client.do_thing_calls
    assert [topic for _, topic, _ in calls] == [
        "2nd_appmode",
        "2nd_sosdown",
        "sosdown",
        "alarmcancel",
        "2nd_sosparam",
        "2nd_appactivate",
        "2nd_appinstallguide",
        "2nd_signaltest_DEV123",
        "testir",
        "2nd_driveway",
    ]
    assert calls[0][2]["state"]["desired"] == {
        "shadow": "appMode",
        "stationSN": "BASE123",
        "userId": "user-id",
        "userParam": "source=1",
        "source": "1",
        "safeMode": "away",
        "forceArm": "1",
    }
    assert calls[1][2]["state"]["desired"]["sosType"] == "2"
    assert calls[2][2]["state"]["desired"]["sosStatus"] == "0"
    assert calls[3][2]["state"]["desired"]["shadow"] == "alarmCancel"
    assert calls[4][2]["state"]["desired"]["sosSound"] == "3"
    assert calls[5][2]["state"]["desired"]["activate"] == "1"
    assert calls[6][2]["state"]["desired"]["detcSens"] == "2"
    assert calls[7][2]["state"]["desired"]["testTime"] == "9"
    assert calls[8][2]["state"]["desired"] == {
        "shadow": "testIR",
        "stationSN": "BASE123",
        "deviceSN": "DEV123",
        "devType": "SMS01",
        "testIR": "0",
    }
    assert calls[9][2]["state"]["desired"]["mute"] == "1"


def test_apk_config_and_alarm_compatibility_methods_validate_and_write_payloads():
    station = _station("SBS50")
    device = FakeEntity(station=station, entity_type=EntityType.WATER)
    device.type = "SWS0A"
    client = RecordingClient()

    asyncio.run(client.set_device_config(device, ledBrt="2"))
    asyncio.run(client.set_alarm_volume(device, 75, alarm_tone="2", mute="0"))
    asyncio.run(client.set_voice_volume(station, 33))
    asyncio.run(client.set_fire_drill(device, alarm_type="1", alarm_vol="75"))
    asyncio.run(client.set_light_group_power(station, "group-1", ["LIGHT1"], True))
    asyncio.run(client.mute_water(device, trigger_source="leak"))
    asyncio.run(client.mute_temperature_humidity(device, sensor_type="STH0B"))

    calls = client.do_thing_calls
    assert [topic for _, topic, _ in calls] == [
        "2nd_cfg_DEV123",
        "2nd_cfg_DEV123",
        "2nd_cfg_BASE123",
        "2nd_firedrill",
        "2nd_grouppower",
        "2nd_appwater",
        "2nd_appmute",
    ]
    assert calls[0][2]["state"]["desired"] == {
        "shadow": "infoDev",
        "stationSN": "BASE123",
        "deviceSN": "DEV123",
        "ledBrt": "2",
    }
    assert calls[1][2]["state"]["desired"]["alarmVol"] == "75"
    assert calls[1][2]["state"]["desired"]["alarmTone"] == "2"
    assert calls[2][2]["state"]["desired"] == {
        "shadow": "infoBase",
        "stationSN": "BASE123",
        "voiceVol": "33",
    }
    assert calls[3][2]["state"]["desired"]["drill"] == "1"
    assert calls[3][2]["state"]["desired"]["deviceType"] == "SWS0A"
    assert calls[4][2]["state"]["desired"]["devs"] == ["LIGHT1"]
    assert calls[4][2]["state"]["desired"]["isOn"] == "1"
    assert calls[5][2]["state"]["desired"]["triggerSource"] == "leak"
    assert calls[6][2]["state"]["desired"]["type"] == "STH0B"

    try:
        asyncio.run(client.set_voice_volume(station, 101))
    except XSenseError:
        pass
    else:
        raise AssertionError("volume above 100 should fail")

    try:
        asyncio.run(client.set_motion_test(device, active="yes"))
    except XSenseError:
        pass
    else:
        raise AssertionError("non boolean-like values should fail")


def test_action_uses_resolved_app_shadow_definition():
    house = House(None, "house-id", "Home", "US", "us-east-1", "mqtt.example")
    station = Station(
        house,
        stationId="station-id",
        stationSn="BASE123",
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
    client = RecordingClient()

    asyncio.run(client.action(device, "test"))

    target, topic, payload = client.do_thing_calls[0]
    desired = payload["state"]["desired"]
    assert target is station
    assert topic
    assert desired["deviceSN"] == "DEV123"
    assert desired["stationSN"] == "BASE123"
    assert desired["userId"] == "user-id"
    assert desired["shadow"]


def test_station_less_xs01_wx_action_uses_station_as_its_own_target():
    house = House(None, "house-id", "Home", "US", "us-east-1", "mqtt.example")
    station = Station(
        house,
        stationId="station-id",
        stationSn="EN123",
        stationName="Standalone Smoke",
        category="XS01-WX",
    )
    station.set_data({"smokeEdition": 9})
    client = RecordingClient()

    asyncio.run(client.action(station, "mute"))

    target, topic, payload = client.do_thing_calls[0]
    desired = payload["state"]["desired"]
    assert target.shadow_name == "XS01-WX-EN123"
    assert topic == "2nd_appmute"
    assert desired["deviceSN"] == "EN123"
    assert desired["stationSN"] == "EN123"
    assert desired["shadow"] == "appMute"
    assert desired["muteType"] == "0"


def test_has_action_only_returns_true_for_known_resolvable_actions():
    house = House(None, "house-id", "Home", "US", "us-east-1", "mqtt.example")
    station = Station(
        house,
        stationId="station-id",
        stationSn="BASE123",
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
    camera = Device(
        station,
        deviceId="camera-id",
        deviceSn="CAM123",
        deviceType="SSC0A",
        deviceName="Camera",
    )
    client = RecordingClient()

    assert client.has_action(device, "test") is True
    assert client.has_action(device, "mute") is True
    assert client.has_action(device, "firedrill") is True
    assert client.has_action(device, "missing") is False
    assert client.has_action(camera, "test") is False


def test_has_action_requires_resolvable_device_identity():
    station = _station("SBS50")
    device = FakeEntity(station=station, entity_type=EntityType.SMOKE)
    device.type = "SC07-MR"
    device.sn = ""
    client = RecordingClient()

    assert client.has_action(device, "test") is False
