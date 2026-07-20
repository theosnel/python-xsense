import asyncio

from xsense.async_xsense import (
    AsyncXSense,
    _camera_ai_assistant_data,
    _camera_ai_notification_data,
    _camera_ai_notification_payload,
    _camera_audio_data,
    _camera_config_data,
    _camera_settings_options_data,
)


class FakeCamera:
    def __init__(self, data=None):
        self.sn = "CAM123"
        self.type = "SSC0A"
        self.data = dict(data or {})

    def set_data(self, values):
        self.data.update(values)


class StubAddxClient(AsyncXSense):
    def __init__(self):
        super().__init__(session=None)
        self.calls = []

    async def addx_call(self, endpoint: str, **kwargs):
        self.calls.append((endpoint, kwargs))
        return {}


def test_camera_config_data_normalizes_boolean_and_default_fields():
    data = _camera_config_data(
        {
            "needMotion": 1,
            "needVideo": 0,
            "needNightVision": None,
            "videoSeconds": 0,
            "voiceVolumeSwitch": 1,
            "cooldown": {
                "deviceSupport": 1,
                "userEnable": 0,
                "value": "30",
                "notCloseValues": [10, 30, 60],
            },
        }
    )

    assert data["needMotion"] is True
    assert data["needVideo"] is False
    assert data["needNightVision"] is None
    assert data["videoSeconds"] == -1
    assert data["voiceVolumeSwitch"] is True
    assert data["cooldownSupported"] is True
    assert data["cooldownEnabled"] is False
    assert data["cooldownValue"] == "30"
    assert data["cooldownOptions"] == [10, 30, 60]


def test_camera_form_and_audio_option_parsers():
    assert _camera_settings_options_data(
        {
            "deviceFormOptions": {
                "videoSeconds": [
                    {"value": 10, "enabled": True},
                    {"value": 20, "enabled": False},
                    {"value": 30},
                ],
                "cooldown_in_s": [
                    {"value": 15, "enabled": True},
                    {"value": 60, "enabled": False},
                ],
            }
        }
    ) == {
        "videoSecondsOptions": [
            {"value": 10, "enabled": True},
            {"value": 20, "enabled": False},
            {"value": 30, "enabled": None},
        ],
        "videoSecondsValues": [10],
        "cooldownOptionDetails": [
            {"value": 15, "enabled": True},
            {"value": 60, "enabled": False},
        ],
        "cooldownOptions": [15],
    }

    assert _camera_audio_data(
        {
            "deviceAudio": {
                "doorBellRingKey": "ding",
                "supportDoorBellRingKey": [{"id": "ding"}, {"id": "dong"}, {}],
                "liveAudioToggleOn": 1,
                "liveSpeakerVolume": 55,
                "recordingAudioToggleOn": 0,
            }
        }
    ) == {
        "doorBellRingKey": "ding",
        "doorBellRingKeyOptions": ["ding", "dong"],
        "liveAudioToggleOn": True,
        "liveSpeakerVolume": 55,
        "recordingAudioToggleOn": False,
    }


def test_update_camera_config_uses_app_user_config_payload():
    camera = FakeCamera(
        {
            "motionSensitivity": 7,
            "videoSeconds": 0,
            "supportRocker": False,
            "alarmSeconds": 0,
            "nightThresholdLevel": 4,
        }
    )
    client = StubAddxClient()

    asyncio.run(
        client.update_camera_config(
            camera,
            needMotion=True,
            needVideo=True,
            needAlarm=True,
            needNightVision=True,
            deviceCallToggleOn=1,
            ignoredField=True,
        )
    )

    assert client.calls == [
        (
            "/device/updateuserconfig",
            {
                "serialNumber": "CAM123",
                "needMotion": 1,
                "needVideo": 1,
                "needAlarm": 1,
                "needNightVision": 1,
                "deviceCallToggleOn": True,
                "motionSensitivity": 7,
                "videoSeconds": -1,
                "alarmSeconds": 5,
                "nightThresholdLevel": 4,
            },
        )
    ]
    assert camera.data["needMotion"] is True
    assert camera.data["ignoredField"] is True


def test_camera_audio_and_direct_control_helpers_use_app_endpoints():
    camera = FakeCamera(
        {
            "doorBellRingKey": "ding",
            "liveAudioToggleOn": True,
            "liveSpeakerVolume": 30,
            "recordingAudioToggleOn": False,
        }
    )
    client = StubAddxClient()

    asyncio.run(client.update_camera_audio(camera, liveSpeakerVolume=45))
    asyncio.run(client.update_camera_recording_resolution(camera, "1920x1080"))
    asyncio.run(client.update_camera_default_codec(camera, "H265"))
    asyncio.run(client.update_camera_cooldown(camera, user_enable=True, value=60))
    asyncio.run(client.update_camera_sleep(camera, enabled=True))
    asyncio.run(client.update_camera_sleep(camera, enabled=False))

    assert client.calls == [
        (
            "/device/config/updatedeviceaudio",
            {
                "serialNumber": "CAM123",
                "deviceAudio": {
                    "doorBellRingKey": "ding",
                    "liveAudioToggleOn": True,
                    "liveSpeakerVolume": 45,
                    "recordingAudioToggleOn": False,
                },
            },
        ),
        (
            "/device/updaterecresolution",
            {"serialNumber": "CAM123", "recResolution": "1920x1080"},
        ),
        (
            "/device/config/updatedefaultcodec",
            {"serialNumber": "CAM123", "defaultCodec": "H265"},
        ),
        (
            "/device/updateCooldown",
            {"serialNumber": "CAM123", "cooldown": {"userEnable": True, "value": 60}},
        ),
        (
            "/device/dormancy/switch",
            {"serialNumber": "CAM123", "dormancySwitch": 1},
        ),
        (
            "/device/dormancy/switch",
            {"serialNumber": "CAM123", "dormancySwitch": 0},
        ),
    ]
    assert camera.data["liveSpeakerVolume"] == 45
    assert camera.data["recResolution"] == "1920x1080"
    assert camera.data["defaultCodec"] == "H265"
    assert camera.data["cooldownEnabled"] is True
    assert camera.data["cooldownValue"] == 60
    assert camera.data.get("deviceStatus") is None


def test_camera_ai_notification_parsing_and_payload_shape():
    parsed = _camera_ai_notification_data(
        {
            "list": [
                {"name": "person", "choice": True},
                {
                    "name": "vehicle",
                    "subEvent": [
                        {"name": "vehicle_enter", "choice": True},
                        {"name": "vehicle_out", "choice": False},
                    ],
                },
                {"name": "package", "choice": False},
            ]
        }
    )

    assert parsed["aiNotificationPerson"] is True
    assert parsed["aiNotificationVehicleEnter"] is True
    assert parsed["aiNotificationVehicleOut"] is False
    assert parsed["aiNotificationPackageExist"] is False
    assert parsed["aiNotificationSupportedTypes"] == [
        "package_drop_off",
        "package_exist",
        "package_pick_up",
        "person",
        "vehicle_enter",
        "vehicle_out",
    ]
    assert _camera_ai_notification_payload(
        {"person", "vehicle_enter", "package_pick_up"}
    ) == {
        "vehicle": ["vehicle_enter"],
        "package": ["package_pick_up"],
        "person": [],
    }


def test_camera_ai_assistant_data_and_update_payload():
    parsed = _camera_ai_assistant_data(
        {
            "data": [
                {
                    "serialNumber": "OTHER",
                    "list": [{"eventObject": "person", "checked": True}],
                },
                {
                    "serialNumber": "CAM123",
                    "list": [
                        {"eventObject": "person", "checked": True},
                        {"eventObject": "package", "checked": False},
                    ],
                },
            ]
        },
        "CAM123",
    )

    assert parsed == {
        "aiAssistantPerson": True,
        "aiAssistantPackage": False,
        "aiAssistantSupportedTypes": ["person", "package"],
    }

    camera = FakeCamera(parsed)
    client = StubAddxClient()
    asyncio.run(client.update_camera_ai_assistant(camera, "package", True))

    assert client.calls == [
        (
            "/aiAssist/updateEventObjectSwitch",
            {
                "serialNumber": "CAM123",
                "list": [{"checked": True, "eventObject": "package"}],
            },
        )
    ]
    assert camera.data["aiAssistantPackage"] is True


def test_update_camera_ai_notification_writes_full_payload():
    camera = FakeCamera(
        {
            "aiNotificationPerson": True,
            "aiNotificationVehicleEnter": False,
            "aiNotificationVehicleOut": True,
        }
    )
    client = StubAddxClient()

    asyncio.run(client.update_camera_ai_notification(camera, "vehicle_enter", True))

    assert client.calls == [
        (
            "/device/updateMessageNotification/v1",
            {
                "serialNumber": "CAM123",
                "eventObjectType": {
                    "vehicle": ["vehicle_enter", "vehicle_out"],
                    "package": [],
                    "person": [],
                },
            },
        )
    ]
    assert camera.data["aiNotificationVehicleEnter"] is True
