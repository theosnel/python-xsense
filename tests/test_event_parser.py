from xsense.event_parser import (
    camera_event_history_event_key,
    camera_event_history_records,
    camera_event_history_station_data,
    is_presence_topic,
    is_self_test_topic,
    mqtt_identifier_candidates,
    mqtt_reported_data,
    mqtt_topic_kind,
    normalize_self_test_report,
    normalize_self_test_result,
)


def test_mqtt_camera_motion_event_preserves_event_time():
    data = mqtt_reported_data(
        {
            "eventType": 92,
            "eventTime": "20260614221512",
            "eventData": {
                "serialNumber": "camera-sn",
                "deviceName": "Front",
            },
        }
    )

    assert data["serialNumber"] == "camera-sn"
    assert data["eventType"] == 92
    assert data["time"] == "20260614221512"
    assert data["eventTime"] == "20260614221512"
    assert "isMoved" not in data
    assert "lastMotionTime" not in data


def test_mqtt_camera_motion_event_accepts_json_event_data():
    data = mqtt_reported_data(
        {
            "eventType": "motion_detection",
            "eventTime": "20260614221612",
            "eventData": '{"serialNumber":"camera-sn","isMoved":"0"}',
        }
    )

    assert data["serialNumber"] == "camera-sn"
    assert data["eventType"] == "motion_detection"
    assert data["eventTime"] == "20260614221612"
    assert data["isMoved"] == "0"


def test_mqtt_camera_ai_event_maps_detection_objects():
    data = mqtt_reported_data(
        {
            "eventTime": "20260614231512",
            "eventData": {
                "serialNumber": "camera-sn",
                "eventItems": [
                    {"eventType": "person", "eventTime": "20260612120000"}
                ],
            },
        }
    )

    assert data["lastAiDetection"] == "person"
    assert data["personDetected"] is True
    assert data["petDetected"] is False
    assert data["vehicleDetected"] is False
    assert data["packageDetected"] is False
    assert data["otherDetected"] is False
    assert data["lastPersonDetectionTime"] == "20260612120000"


def test_mqtt_camera_ai_event_groups_vehicle_and_package_objects():
    data = mqtt_reported_data(
        {
            "eventTime": "20260614231612",
            "eventData": {
                "serialNumber": "camera-sn",
                "eventItems": [
                    {"eventType": "vehicle_held_up", "eventTime": "20260612120000"},
                    {"eventType": "package_pick_up", "eventTime": "20260612120001"},
                ],
            },
        }
    )

    assert data["lastAiDetection"] == "package_pick_up,vehicle_held_up"
    assert data["vehicleDetected"] is True
    assert data["packageDetected"] is True
    assert data["vehicleHeldUpDetected"] is True
    assert data["packagePickUpDetected"] is True
    assert data["vehicleEnterDetected"] is False
    assert data["lastVehicleDetectionTime"] == "20260612120000"
    assert data["lastPackageDetectionTime"] == "20260612120001"


def test_mqtt_camera_ai_event_accepts_event_object_type_payload():
    data = mqtt_reported_data(
        {
            "eventTime": "20260614231712",
            "eventData": {
                "serialNumber": "camera-sn",
                "eventObjectType": {
                    "person": [],
                    "pet": [],
                    "vehicle": ["vehicle_enter"],
                    "package": ["package_exist"],
                },
            },
        }
    )

    assert data["personDetected"] is True
    assert data["petDetected"] is True
    assert data["vehicleDetected"] is True
    assert data["packageDetected"] is True
    assert data["lastAiDetection"] == "package_exist,person,pet,vehicle_enter"
    assert data["vehicleEnterDetected"] is True
    assert data["packageExistDetected"] is True


def test_mqtt_camera_ai_plan_event_uses_dispatch_device_identity():
    data = mqtt_reported_data(
        {
            "userId": "user-id",
            "eventType": "ai_event",
            "eventTime": "20260614230000",
            "eventData": {
                "serverId": "service-id",
                "dispatchDevs": [
                    {
                        "stationSn": "station-sn",
                        "deviceSn": "camera-sn",
                        "deviceType": "SSC0A",
                        "eventTime": "20260614230100",
                    }
                ],
                "eventItems": [
                    {"eventType": "person", "eventTime": "20260614230200"}
                ],
            },
        }
    )

    assert data["stationSN"] == "station-sn"
    assert data["deviceSN"] == "camera-sn"
    assert data["serialNumber"] == "camera-sn"
    assert data["lastAiDetection"] == "person"
    assert data["lastPersonDetectionTime"] == "20260614230200"


def test_mqtt_dispatch_device_identity_accepts_station_and_device_aliases():
    data = mqtt_reported_data(
        {
            "eventData": {
                "dispatchDevs": [
                    {
                        "stationSerialNumber": "station-sn",
                        "devSerialNumber": "device-sn",
                        "eventTime": "20260614230100",
                    }
                ]
            },
        }
    )

    assert data["stationSN"] == "station-sn"
    assert data["deviceSN"] == "device-sn"
    assert data["serialNumber"] == "device-sn"
    assert data["time"] == "20260614230100"


def test_identifier_candidates_walk_nested_json_payloads():
    assert mqtt_identifier_candidates(
        {
            "eventData": '{"dispatchDevs":[{"stationSn":"station-sn","deviceSn":"camera-sn"}]}'
        }
    ) == ["station-sn", "camera-sn"]


def test_camera_event_history_records_and_station_data():
    history = {
        "data": {
            "list": [
                {
                    "serialNumber": "CAM123",
                    "traceId": "trace-1",
                    "timestamp": 1_718_000_000_000,
                    "videoEvent": "motion",
                    "eventInfoList": [
                        {"eventType": "person", "eventTime": "20260614230200"}
                    ],
                },
                "bad-record",
            ]
        }
    }

    records = camera_event_history_records(history)
    data = camera_event_history_station_data(records[0])

    assert len(records) == 1
    assert camera_event_history_event_key(records[0]) == "camera-event:CAM123:trace-1"
    assert data["serialNumber"] == "CAM123"
    assert data["deviceSN"] == "CAM123"
    assert data["eventType"] == "motion"
    assert data["lastAiDetection"] == "person"
    assert data["personDetected"] is True
    assert data["lastPersonDetectionTime"] == "20260614230200"


def test_mqtt_topic_kind_classifies_xsense_topics():
    assert mqtt_topic_kind("$aws/events/presence/connected/thing") == "presence"
    assert mqtt_topic_kind("@xsense/events/aiplan/user") == "ai_plan"
    assert mqtt_topic_kind("@xsense/events/motion/house") == "house_event"
    assert mqtt_topic_kind("$aws/things/thing/shadow/name/info/update") == "shadow"
    assert mqtt_topic_kind("other/topic") == "other"
    assert is_presence_topic("$aws/events/presence/connected/thing") is True
    assert is_presence_topic("@xsense/events/motion/house") is False


def test_self_test_topic_detection_matches_app_report_topics():
    assert is_self_test_topic("$aws/things/base/shadow/name/2nd_selftestup/update")
    assert is_self_test_topic("$aws/things/base/shadow/name/selftestup_v2/update")
    assert is_self_test_topic("$aws/things/base/shadow/name/device_testup/update")
    assert not is_self_test_topic("$aws/things/base/shadow/name/info/update")


def test_normalize_self_test_report_maps_result_and_time_fields():
    data = {"testResult": "passed", "timestamp": "20260625010203"}

    normalize_self_test_report(data)

    assert data["lastSelfTest"] == "0"
    assert data["lastSelfTestTime"] == "20260625010203"


def test_normalize_self_test_result_preserves_numeric_values():
    assert normalize_self_test_result("failed") == "1"
    assert normalize_self_test_result("error") == "1"
    assert normalize_self_test_result("ok") == "0"
    assert normalize_self_test_result(0) == 0
