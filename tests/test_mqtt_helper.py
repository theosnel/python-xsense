import json

import pytest

from xsense import mqtt_helper


def test_mqtt_helper_defers_tls_context_loading_until_connect_setup(monkeypatch):
    calls = []
    clients = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.contexts = []
            self.ws_paths = []
            clients.append(self)

        def username_pw_set(self, username, password):
            self.username = username
            self.password = password

        def tls_set_context(self, context):
            self.contexts.append(context)

        def ws_set_options(self, path):
            self.ws_paths.append(path)

    def fake_create_default_context():
        calls.append("created")
        return "ssl-context"

    monkeypatch.setattr(mqtt_helper.mqtt_client, "Client", FakeClient)
    monkeypatch.setattr(
        mqtt_helper.ssl, "create_default_context", fake_create_default_context
    )

    helper = mqtt_helper.MQTTHelper(
        signer=type(
            "Signer",
            (),
            {"presign_url": lambda self, *args: "wss://mqtt.example/mqtt?sig=abc"},
        )(),
        house=type(
            "House",
            (),
            {"mqtt_server": "mqtt.example", "mqtt_region": "us-east-1"},
        )(),
    )

    assert calls == []
    assert clients[0].contexts == []
    assert clients[0].ws_paths == []

    helper.prepare_connection()

    assert calls == ["created"]
    assert clients[0].contexts == ["ssl-context"]
    assert clients[0].ws_paths == ["/mqtt?sig=abc"]

    helper.prepare_connection()

    assert calls == ["created"]
    assert clients[0].contexts == ["ssl-context"]
    assert clients[0].ws_paths == ["/mqtt?sig=abc", "/mqtt?sig=abc"]


def _helper_with_client(client):
    helper = object.__new__(mqtt_helper.MQTTHelper)
    helper.client = client
    return helper


def test_mqtt_helper_subscribe_uses_app_qos1_by_default():
    subscribed = []

    class FakeClient:
        def subscribe(self, topic, qos=0):
            subscribed.append((topic, qos))
            return "subscribed"

    helper = _helper_with_client(FakeClient())

    assert helper.subscribe("topic/name") == "subscribed"
    assert subscribed == [("topic/name", 1)]


def test_mqtt_helper_publish_uses_compact_utf8_json():
    published = []

    class FakeClient:
        def publish(self, topic, payload, qos=0, retain=False):
            published.append((topic, payload, qos, retain))
            return "published"

    helper = _helper_with_client(FakeClient())
    payload = {"label": "中文", "enabled": True}

    assert helper.publish("topic", payload) == "published"
    assert published == [
        (
            "topic",
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            0,
            False,
        )
    ]


def test_mqtt_topic_helpers_match_aws_and_app_topics():
    assert (
        mqtt_helper.shadow_update_topic("thing", "infoDev")
        == "$aws/things/thing/shadow/name/infoDev/update"
    )
    assert (
        mqtt_helper.shadow_wildcard_topic("thing")
        == "$aws/things/thing/shadow/name/+/update"
    )
    assert mqtt_helper.presence_topic("thing") == "$aws/events/presence/+/thing"
    assert mqtt_helper.house_event_topic("house") == "@xsense/events/+/house"


def test_mqtt_payload_parser_and_shadow_ack_filtering():
    assert mqtt_helper.parse_message_payload(b'{"state":{"reported":{"on":"1"}}}') == {
        "state": {"reported": {"on": "1"}}
    }
    assert mqtt_helper.parse_message_payload(None) == {}
    assert mqtt_helper.parse_message_payload({"already": "dict"}) == {"already": "dict"}
    assert mqtt_helper.should_ignore_shadow_topic(
        "$aws/things/thing/shadow/name/infoDev/update/accepted"
    )
    assert not mqtt_helper.should_ignore_shadow_topic(
        "$aws/things/thing/shadow/name/infoDev/update"
    )


def test_live_update_topics_include_house_station_and_presence_topics():
    station = type("Station", (), {"shadow_name": "SBS50BASE123"})()
    house = type(
        "House",
        (),
        {
            "house_id": "house-id",
            "stations": {"station": station},
        },
    )()
    helper = object.__new__(mqtt_helper.MQTTHelper)
    helper.house = house

    assert helper.live_update_topics() == [
        "@xsense/events/+/house-id",
        "$aws/things/house-id/shadow/name/+/update",
        "$aws/things/SBS50BASE123/shadow/name/+/update",
        "$aws/events/presence/+/SBS50BASE123",
    ]


def test_temp_data_request_requires_user_and_device_serials():
    helper = object.__new__(mqtt_helper.MQTTHelper)
    station = type(
        "Station",
        (),
        {
            "sn": "BASE123",
            "shadow_name": "SBS50BASE123",
            "devices": {
                "one": type("Device", (), {"sn": "TEMP1", "type": "STH0B"})(),
                "two": type("Device", (), {"sn": "SMOKE1", "type": "XS01-M"})(),
            },
        },
    )()

    with pytest.raises(ValueError, match="user_id is required"):
        helper.build_temp_data_request(station)

    payload = helper.build_temp_data_request(station, user_id="user-id")

    desired = payload["state"]["desired"]
    assert desired["shadow"] == "appTempData"
    assert desired["deviceSN"] == ["TEMP1"]
    assert desired["stationSN"] == "BASE123"
    assert desired["userId"] == "user-id"
    assert desired["timeoutM"] == "5"
    assert helper.temp_data_topic(station) == (
        "$aws/things/SBS50BASE123/shadow/name/2nd_apptempdata/update"
    )
