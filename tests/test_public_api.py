import importlib
from importlib import metadata


import xsense
from xsense import AsyncXSense, Device, House, MQTTHelper, Station, XSense
from xsense.base import XSenseBase


def test_top_level_exports_current_and_legacy_clients():
    assert xsense.__version__ == "0.1.0"
    assert xsense.__all__ == [
        "AsyncXSense",
        "XSense",
        "camera_addx_serial",
        "camera_for_identifier",
    "camera_identifiers",
    "camera_matches_identifier",
    "camera_primary_identifiers",
    "cameras_share_identity",
    "Device",
    "House",
        "MQTTHelper",
        "Station",
        "__version__",
    ]
    assert AsyncXSense is xsense.AsyncXSense
    assert Device is xsense.Device
    assert House is xsense.House
    assert XSense is xsense.XSense
    assert MQTTHelper is xsense.MQTTHelper
    assert Station is xsense.Station


def test_distribution_metadata_matches_upstream_package():
    assert metadata.version("python-xsense") == xsense.__version__
    dist = metadata.metadata("python-xsense")
    assert dist["Name"] == "python-xsense"
    assert dist["Requires-Python"] == ">=3.10"
    assert dist.get_all("Provides-Extra") == ["test", "dev"]
    requirements = metadata.requires("python-xsense") or []
    assert "paho-mqtt<3,>=2.1.0" in requirements
    assert "requests" in requirements


def test_legacy_sync_client_module_remains_importable():
    assert importlib.import_module("xsense.xsense").XSense is XSense

def test_cognito_login_keeps_sync_login_compatibility_alias():
    assert XSenseBase._cognito_login is XSenseBase.sync_login


def test_async_client_exposes_current_camera_api_surface():
    assert hasattr(AsyncXSense, "update_camera_sleep")
    assert hasattr(AsyncXSense, "update_camera_cooldown")
    assert hasattr(AsyncXSense, "update_camera_recording_resolution")
    assert hasattr(AsyncXSense, "update_camera_default_codec")

    assert hasattr(AsyncXSense, "retrieve_camera_local_videos")
    assert hasattr(AsyncXSense, "play_camera_local_video")
    assert hasattr(AsyncXSense, "stop_camera_local_video")

def test_event_parser_has_explicit_public_exports():
    event_parser = importlib.import_module("xsense.event_parser")

    assert "mqtt_reported_data" in event_parser.__all__
    assert "camera_event_records" in event_parser.__all__
    assert "apply_apk_ai_detection_aliases" in event_parser.__all__
    assert "normalize_self_test_report" in event_parser.__all__
    assert "is_presence_topic" in event_parser.__all__


def test_webrtc_signal_exports_current_relay_surface():
    webrtc_signal = importlib.import_module("xsense.webrtc_signal")

    assert hasattr(webrtc_signal, "XSenseWebRTCTicket")
    assert hasattr(webrtc_signal, "XSenseWebRTCSignalSession")
    assert hasattr(webrtc_signal, "make_sdp_offer_payload")
    assert hasattr(webrtc_signal, "make_ice_candidate_payload")
    assert hasattr(webrtc_signal, "parse_signal_message")
    assert hasattr(webrtc_signal, "make_sd_video_list_command_payload")
    assert hasattr(webrtc_signal, "make_start_sd_playback_command_payload")
    assert hasattr(webrtc_signal, "make_stop_sd_playback_command_payload")


def test_legacy_sync_client_preserves_app_request_shape():
    class SyncResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"reCode": 200, "reData": {"ok": True}}

    class SyncSession:
        def __init__(self):
            self.calls = []
            self.closed = False

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return SyncResponse()

        def close(self):
            self.closed = True

    session = SyncSession()
    with XSense(session) as client:
        assert client.api_call("104001", unauth=True, houseId="house-id") == {"ok": True}

    assert not session.closed
    url, request = session.calls[0]
    assert url == "https://api.x-sense-iot.com/app"
    assert request["headers"] is None
    assert request["json"] == {
        "houseId": "house-id",
        "clientType": "2",
        "mac": "abcdefg",
        "appVersion": "v1.40.0_20260612",
        "bizCode": "104001",
        "appCode": "1400",
    }


def test_legacy_sync_client_retains_0_0_public_methods():
    legacy_methods = {
        "close",
        "api_call",
        "get_house",
        "get_thing",
        "do_thing",
        "login",
        "refresh",
        "init",
        "load_aws",
        "load_all",
        "get_client_info",
        "get_aws_tokens",
        "get_houses",
        "get_rooms",
        "get_stations",
        "get_history",
        "get_history_month",
        "get_station_history",
        "get_station_history_month",
        "get_security_history",
        "get_sth_history",
        "get_co_ppm_history",
        "get_co_ppm_history_details",
        "get_house_state",
        "get_alarm_state",
        "get_station_state",
        "get_state",
        "set_state",
        "action",
    }

    assert legacy_methods <= set(dir(XSense))


def test_legacy_standalone_test_action_descriptor_remains_available():
    from types import SimpleNamespace

    from xsense.entity_map import SATestAction

    action = SATestAction()
    assert action["action"] == "test"
    assert action["shadow"] == "appSelfTest"
    assert action["topic"](SimpleNamespace(sn="device-id")) == "appselftest_device-id"
