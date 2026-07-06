import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
from types import SimpleNamespace

import pytest

from xsense.async_xsense import AsyncXSense
from xsense.base import XSenseBase, shadow_update_body
from xsense.exceptions import APIFailure, SessionExpired


def _test_jwt(claims):
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload = (
        base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    )
    return f"{header}.{payload}."


def test_restore_session_sets_user_id_code_from_token():
    client = XSenseBase()

    client.restore_session(
        "user@example.com",
        "access",
        "refresh",
        _test_jwt({"user_id_code": "user-id-code"}),
    )

    assert client.user_id_code == "user-id-code"


def test_restore_session_ignores_malformed_user_id_code_token():
    client = XSenseBase()

    client.restore_session("user@example.com", "bad-token", "refresh", "also.bad")

    assert client.user_id_code is None


def test_parse_refresh_result_updates_user_id_code():
    client = XSenseBase()

    client._parse_refresh_result(
        {
            "AccessToken": _test_jwt({"user_id_code": "access-user-code"}),
            "ExpiresIn": 3600,
        }
    )

    assert client.user_id_code == "access-user-code"


def test_calculate_mac_uses_compact_app_json_for_container_values():
    client = XSenseBase()
    client.clientsecret = b"secret"
    data = {
        "enabled": True,
        "empty": [],
        "missing": None,
        "labels": ["front", "中文"],
        "settings": {"label": "中文", "enabled": False},
        "items": [{"a": 1}],
    }

    expected_input = (
        'true'
        'null'
        'front'
        '中文'
        '{"label":"中文","enabled":false}'
        '[{"a":1}]'
    )
    expected = hashlib.md5(expected_input.encode("utf-8") + b"secret").hexdigest()

    assert client._calculate_mac(data) == expected


class AsyncFakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self._payload = payload or {"reCode": 200, "reData": {"ok": True}}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def json(self):
        return self._payload

    async def text(self):
        return json.dumps(self._payload)


class AsyncFakeSession:
    closed = False

    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self.responses:
            return self.responses.pop(0)
        return AsyncFakeResponse()

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self.responses:
            return self.responses.pop(0)
        return AsyncFakeResponse()


def test_async_app_call_uses_current_app_metadata_and_mac():
    session = AsyncFakeSession()
    client = AsyncXSense(session)
    client.clientsecret = b"secret"
    client.access_token = "access-token"
    client.access_token_expiry = datetime(2099, 1, 1, tzinfo=timezone.utc)

    result = asyncio.run(client.api_call("701001", userId="user-id-code"))

    assert result == {"ok": True}
    call = session.calls[0]
    assert call["url"] == "https://api.x-sense-iot.com/app"
    assert call["headers"] == {"Authorization": "access-token"}
    assert call["json"]["userId"] == "user-id-code"
    assert call["json"]["bizCode"] == "701001"
    assert call["json"]["appCode"] == "1360"
    assert call["json"]["appVersion"] == "v1.36.0_20260130"
    assert call["json"]["clientType"] == "2"
    assert call["json"]["mac"] == client._calculate_mac({"userId": "user-id-code"})


class RefreshingClient(AsyncXSense):
    def __init__(self, session):
        super().__init__(session)
        self.refreshes = 0

    async def refresh(self):
        self.refreshes += 1
        self.access_token = f"refreshed-token-{self.refreshes}"
        self.access_token_expiry = datetime(2099, 1, 1, tzinfo=timezone.utc)


def test_async_app_call_refreshes_expiring_access_token_before_request():
    session = AsyncFakeSession()
    client = RefreshingClient(session)
    client.clientsecret = b"secret"
    client.access_token = "old-token"
    client.access_token_expiry = datetime.now(timezone.utc)

    result = asyncio.run(client.api_call("701001", userId="user-id-code"))

    assert result == {"ok": True}
    assert client.refreshes == 1
    assert session.calls[0]["headers"] == {"Authorization": "refreshed-token-1"}


def test_async_app_call_raises_session_expired_for_app_expiry_codes():
    session = AsyncFakeSession(
        [
            AsyncFakeResponse(
                payload={
                    "reCode": 400,
                    "errCode": "10000008",
                    "reMsg": "session expired",
                }
            )
        ]
    )
    client = AsyncXSense(session)
    client.clientsecret = b"secret"
    client.access_token = "access-token"
    client.access_token_expiry = datetime(2099, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(SessionExpired, match="session expired"):
        asyncio.run(client.api_call("701001", userId="user-id-code"))


def test_refresh_updates_tokens_and_user_id_code():
    id_token = _test_jwt({"user_id_code": "user-id-code"})
    session = AsyncFakeSession(
        [
            AsyncFakeResponse(
                payload={
                    "AuthenticationResult": {
                        "IdToken": id_token,
                        "AccessToken": "new-access-token",
                        "RefreshToken": "new-refresh-token",
                        "ExpiresIn": 3600,
                    }
                }
            )
        ]
    )
    client = AsyncXSense(session)
    client.refresh_token = "old-refresh-token"
    client.region = "us-east-1"
    client.clientid = "client-id"
    client.clientsecret = b"client-secret"

    asyncio.run(client.refresh())

    assert client.id_token == id_token
    assert client.access_token == "new-access-token"
    assert client.refresh_token == "new-refresh-token"
    assert client.user_id_code == "user-id-code"
    assert session.calls[0]["url"] == "https://cognito-idp.us-east-1.amazonaws.com"
    assert session.calls[0]["json"]["AuthFlow"] == "REFRESH_TOKEN_AUTH"
    assert session.calls[0]["json"]["AuthParameters"] == {
        "REFRESH_TOKEN": "old-refresh-token",
        "SECRET_HASH": "client-secret",
    }
    assert session.calls[0]["json"]["ClientId"] == "client-id"


def test_refresh_raises_session_expired_on_http_failure():
    session = AsyncFakeSession(
        [AsyncFakeResponse(status=400, payload={"message": "refresh failed"})]
    )
    client = AsyncXSense(session)
    client.refresh_token = "old-refresh-token"
    client.region = "us-east-1"
    client.clientid = "client-id"
    client.clientsecret = b"client-secret"

    with pytest.raises(SessionExpired, match="refresh failed"):
        asyncio.run(client.refresh())


class ShadowSigner:
    def __init__(self):
        self.calls = []

    def sign_headers(self, method, url, region, headers, data):
        self.calls.append((method, url, region, headers, data))
        return {"Authorization": "signed"}


def _shadow_station():
    return SimpleNamespace(
        house=SimpleNamespace(mqtt_region="us-east-1"),
        sn="BASE123",
        type="SBS10",
        shadow_name="BASE123",
    )


def test_shadow_update_body_uses_compact_utf8_json():
    payload = {"state": {"desired": {"label": "中文", "enabled": True}}}

    assert (
        shadow_update_body(payload)
        == '{"state":{"desired":{"label":"中文","enabled":true}}}'
    )


def test_async_do_thing_signs_and_sends_same_serialized_body():
    session = AsyncFakeSession([AsyncFakeResponse(payload={"ok": True})])
    client = AsyncXSense(session)
    client.aws_access_expiry = datetime(2099, 1, 1, tzinfo=timezone.utc)
    client.aws_session_token = "aws-token"
    client.signer = ShadowSigner()
    payload = {"state": {"desired": {"label": "中文", "enabled": True}}}

    result = asyncio.run(client.do_thing(_shadow_station(), "infoDev", payload))

    expected_body = shadow_update_body(payload)
    assert result == {"ok": True}
    assert session.calls[0]["data"] == expected_body
    assert session.calls[0]["headers"]["Authorization"] == "signed"
    assert client.signer.calls[0][4] == expected_body


class RefreshingAwsClient(AsyncXSense):
    def __init__(self, session):
        super().__init__(session)
        self.aws_access_expiry = datetime(2099, 1, 1, tzinfo=timezone.utc)
        self.aws_session_token = "expired-aws-token"
        self.signer = ShadowSigner()
        self.aws_loads = 0

    async def load_aws(self):
        self.aws_loads += 1
        self.aws_session_token = f"fresh-aws-token-{self.aws_loads}"
        self.signer = ShadowSigner()


def test_get_thing_refreshes_aws_token_and_retries_once_after_forbidden():
    session = AsyncFakeSession(
        [
            AsyncFakeResponse(
                status=403,
                payload={"message": "Forbidden", "traceId": "trace"},
            ),
            AsyncFakeResponse(payload={"state": {"reported": {"ok": True}}}),
        ]
    )
    client = RefreshingAwsClient(session)
    station = _shadow_station()

    result = asyncio.run(client.get_thing(station, "infoDev"))

    assert result == {"state": {"reported": {"ok": True}}}
    assert client.aws_loads == 1
    assert len(session.calls) == 2
    assert session.calls[0]["headers"]["X-Amz-Security-Token"] == "expired-aws-token"
    assert session.calls[1]["headers"]["X-Amz-Security-Token"] == "fresh-aws-token-1"


def test_do_thing_refreshes_aws_token_and_retries_once_after_forbidden():
    session = AsyncFakeSession(
        [
            AsyncFakeResponse(status=403, payload={"message": "Forbidden"}),
            AsyncFakeResponse(payload={"ok": True}),
        ]
    )
    client = RefreshingAwsClient(session)
    payload = {"state": {"desired": {"enabled": True}}}

    result = asyncio.run(client.do_thing(_shadow_station(), "infoDev", payload))

    assert result == {"ok": True}
    assert client.aws_loads == 1
    assert len(session.calls) == 2
    assert session.calls[0]["headers"]["X-Amz-Security-Token"] == "expired-aws-token"
    assert session.calls[1]["headers"]["X-Amz-Security-Token"] == "fresh-aws-token-1"


class MissingExpiryAwsClient(RefreshingAwsClient):
    def __init__(self, session):
        super().__init__(session)
        self.aws_access_expiry = None

    def _aws_token_expiring(self):
        return False


def test_do_thing_does_not_retry_forbidden_without_aws_expiry_state():
    session = AsyncFakeSession(
        [AsyncFakeResponse(status=403, payload={"message": "Forbidden"})]
    )
    client = MissingExpiryAwsClient(session)
    payload = {"state": {"desired": {"enabled": True}}}

    with pytest.raises(APIFailure):
        asyncio.run(client.do_thing(_shadow_station(), "infoDev", payload))

    assert client.aws_loads == 0
    assert len(session.calls) == 1


class Sbs50ChildInfoClient(AsyncXSense):
    def __init__(self, responses):
        super().__init__(AsyncFakeSession())
        self.responses = list(responses)
        self.calls = []

    async def get_thing(self, station, page, *, _retry=True):
        self.calls.append((station.shadow_name, page))
        response = self.responses.pop(0)
        self._lastres = response
        return await response.json()


def test_get_state_merges_sbs50_child_info_shadow_once():
    house = SimpleNamespace(house_id="house-id", mqtt_region="us-east-1")
    station = SimpleNamespace(
        house=house,
        type="SBS50",
        sn="BASE123",
        shadow_name="SBS50BASE123",
        devices={
            "water": SimpleNamespace(
                type="SWS51",
                sn="WATER123",
                data={},
                set_data=lambda values: None,
            )
        },
    )
    water = station.devices["water"]

    def set_water_data(values):
        water.data.update(values)

    water.set_data = set_water_data
    client = Sbs50ChildInfoClient(
        [
            AsyncFakeResponse(payload={"state": {"reported": {"devs": {}}}}),
            AsyncFakeResponse(payload={"state": {"reported": {"alarmStatus": "1"}}}),
            AsyncFakeResponse(payload={"state": {"reported": {"devs": {}}}}),
        ]
    )
    client.parse_get_state = lambda _station, _data: None

    asyncio.run(client.get_state(station))
    asyncio.run(client.get_state(station))

    assert water.data == {"alarmStatus": "1"}
    assert client.calls == [
        ("SBS50BASE123", "2nd_mainpage"),
        ("SBS50BASE123", "2nd_info_WATER123"),
        ("SBS50BASE123", "2nd_mainpage"),
    ]


def test_get_house_signs_shadow_read_request():
    session = AsyncFakeSession([AsyncFakeResponse(payload={"state": {"reported": {}}})])
    client = AsyncXSense(session)
    client.aws_access_expiry = datetime(2099, 1, 1, tzinfo=timezone.utc)
    client.aws_session_token = "aws-token"
    client.signer = ShadowSigner()
    house = SimpleNamespace(house_id="house-id", mqtt_region="us-east-1")

    result = asyncio.run(client.get_house(house, "mainpage"))

    assert result == {"state": {"reported": {}}}
    call = session.calls[0]
    assert call["url"] == "https://us-east-1.x-sense-iot.com/things/house-id/shadow?name=mainpage"
    assert call["headers"]["Authorization"] == "signed"
    assert call["headers"]["X-Amz-Security-Token"] == "aws-token"
    method, url, region, headers, body = client.signer.calls[0]
    assert method == "GET"
    assert url == "https://us-east-1.x-sense-iot.com/things/house-id/shadow?name=mainpage"
    assert region == "us-east-1"
    assert headers["Content-Type"] == "application/x-amz-json-1.0"
    assert headers["User-Agent"] == "aws-sdk-iOS/2.26.5 iOS/17.3 nl_NL"
    assert headers["X-Amz-Security-Token"] == "aws-token"
    assert body is None


def test_get_thing_signs_shadow_read_with_station_shadow_name():
    session = AsyncFakeSession([AsyncFakeResponse(payload={"state": {"reported": {}}})])
    client = AsyncXSense(session)
    client.aws_access_expiry = datetime(2099, 1, 1, tzinfo=timezone.utc)
    client.aws_session_token = "aws-token"
    client.signer = ShadowSigner()
    station = _shadow_station()
    station.shadow_name = "shadow-thing-name"

    result = asyncio.run(client.get_thing(station, "infoDev"))

    assert result == {"state": {"reported": {}}}
    call = session.calls[0]
    assert call["url"] == "https://us-east-1.x-sense-iot.com/things/shadow-thing-name/shadow?name=infoDev"
    assert call["headers"]["Authorization"] == "signed"
    assert client.signer.calls[0][0] == "GET"
    assert client.signer.calls[0][1] == call["url"]
    assert client.signer.calls[0][4] is None


class RecordingHistoryClient(AsyncXSense):
    def __init__(self):
        super().__init__()
        self.api_calls = []

    async def api_call(self, code, unauth=False, **kwargs):
        self.api_calls.append((code, kwargs))
        return {"items": []}


def _history_house_station_device():
    house = SimpleNamespace(house_id="house-id")
    station = SimpleNamespace(house=house, entity_id="station-id")
    device = SimpleNamespace(entity_id="device-id")
    return house, station, device


def test_documented_history_helpers_use_app_request_shapes():
    house, station, device = _history_house_station_device()
    client = RecordingHistoryClient()

    assert asyncio.run(
        client.get_daily_history(house, "20260628", "America/St_Johns", "next")
    ) == {"items": []}
    assert asyncio.run(
        client.get_monthly_history("house-id", "202606", "America/St_Johns")
    ) == {"items": []}
    assert asyncio.run(
        client.get_station_history(
            station,
            "20260628",
            "America/St_Johns",
            device=device,
            next_token="next",
        )
    ) == {"items": []}
    assert asyncio.run(
        client.get_station_monthly_history(
            station, "202606", "America/St_Johns", device="device-id"
        )
    ) == {"items": []}
    assert asyncio.run(
        client.get_co_history_days(station, "America/St_Johns", device=device)
    ) == {"items": []}
    assert asyncio.run(
        client.get_co_history_details(
            station, "20260628", "America/St_Johns", device=device
        )
    ) == {"items": []}
    assert asyncio.run(client.get_temperature_history(station, "0", next_token="n")) == {
        "items": []
    }
    assert asyncio.run(client.get_dispatch_history("server-id", "next")) == {
        "items": []
    }

    assert client.api_calls == [
        (
            "104001",
            {
                "houseId": "house-id",
                "dayTime": "20260628",
                "timeZone": "America/St_Johns",
                "nextToken": "next",
            },
        ),
        (
            "104006",
            {
                "houseId": "house-id",
                "hisMonth": "202606",
                "timeZone": "America/St_Johns",
            },
        ),
        (
            "104007",
            {
                "houseId": "house-id",
                "stationId": "station-id",
                "dayTime": "20260628",
                "timeZone": "America/St_Johns",
                "deviceId": "device-id",
                "nextToken": "next",
            },
        ),
        (
            "104008",
            {
                "houseId": "house-id",
                "stationId": "station-id",
                "hisMonth": "202606",
                "timeZone": "America/St_Johns",
                "deviceId": "device-id",
            },
        ),
        (
            "104009",
            {
                "stationId": "station-id",
                "timeZone": "America/St_Johns",
                "deviceId": "device-id",
            },
        ),
        (
            "104010",
            {
                "houseId": "house-id",
                "stationId": "station-id",
                "dayTime": "20260628",
                "timeZone": "America/St_Johns",
                "deviceId": "device-id",
            },
        ),
        (
            "104020",
            {
                "houseId": "house-id",
                "stationId": "station-id",
                "lastTime": "0",
                "nextToken": "n",
            },
        ),
        ("505001", {"serverId": "server-id", "nextToken": "next"}),
    ]


def test_ipc_language_uses_simple_app_language_code():
    from xsense.async_xsense import _ipc_language

    assert _ipc_language("de-DE") == "de"
    assert _ipc_language("pt_BR") == "pt"
    assert _ipc_language("") == "en"
    assert _ipc_language(None) == "en"


def test_ipc_node_type_uses_mqtt_region_prefix():
    from xsense.async_xsense import _ipc_node_type

    assert _ipc_node_type("eu-central-1") == "EU"
    assert _ipc_node_type("us-east-1") == "US"
    assert _ipc_node_type("cn-north-1") == "CN"
    assert _ipc_node_type("Canada") == "US"
    assert _ipc_node_type(None) == "US"


def test_addx_body_uses_app_info():
    client = AsyncXSense()

    body = client._addx_body(
        {"countryNo": "1", "language": "en"},
        {"serialNumber": "CAM123"},
    )

    assert body["serialNumber"] == "CAM123"
    assert body["countryNo"] == "1"
    assert body["language"] == "en"
    assert body["app"] == {
        "appName": "VicoHome",
        "appType": "Android",
        "bundle": "com.ai.vicoo",
        "channelId": 1000,
        "countlyId": "b940908f19b8e858",
        "tenantId": "guard",
        "version": 200700500,
        "versionName": "2.7.5",
    }


def test_ipc_call_uses_current_app_metadata():
    session = AsyncFakeSession(
        [AsyncFakeResponse(payload={"reCode": "200", "reData": {"token": "ipc"}})]
    )
    client = AsyncXSense(session)
    client.clientsecret = b"secret"
    client.access_token = "access-token"
    client.access_token_expiry = datetime(2099, 1, 1, tzinfo=timezone.utc)

    result = asyncio.run(client.ipc_call("C10101", nodeType="US", language="en"))

    assert result == {"token": "ipc"}
    call = session.calls[0]
    assert call["url"] == "https://ipc.x-sense-iot.com/ipc"
    assert call["headers"] == {"Authorization": "access-token"}
    assert call["json"]["nodeType"] == "US"
    assert call["json"]["language"] == "en"
    assert call["json"]["bizCode"] == "C10101"
    assert call["json"]["appCode"] == "1360"
    assert call["json"]["appVersion"] == "v1.36.0_20260130"
    assert call["json"]["clientType"] == "2"


class IpcRegistrationClient(AsyncXSense):
    def __init__(self, *, language=None):
        super().__init__(language=language)
        self.ipc_calls = []

    async def ipc_call(self, code: str, **kwargs):
        self.ipc_calls.append((code, kwargs))
        return {"token": "addx-token", "nodeType": kwargs["nodeType"]}


def test_register_ipc_uses_house_region_language_and_username():
    client = IpcRegistrationClient(language="fr-CA")
    client.username = "user@example.com"
    client.houses = {
        "house-id": SimpleNamespace(house_id="house-id", mqtt_region="eu-central-1")
    }

    result = asyncio.run(client.register_ipc())

    assert result == {"token": "addx-token", "nodeType": "EU"}
    assert client.ipc_calls == [
        (
            "C10101",
            {
                "userName": "user@example.com",
                "nodeType": "EU",
                "language": "fr",
            },
        )
    ]


def test_register_ipc_requires_loaded_house_data():
    client = IpcRegistrationClient()

    with pytest.raises(APIFailure, match="without an X-Sense house"):
        asyncio.run(client.register_ipc())


def test_ai_service_history_uses_app_service_code_and_server_id():
    session = AsyncFakeSession(
        [AsyncFakeResponse(payload={"reCode": "200", "reData": {"items": []}})]
    )
    client = AsyncXSense(session)
    client.clientsecret = b"secret"
    client.access_token = "access-token"
    client.access_token_expiry = datetime(2099, 1, 1, tzinfo=timezone.utc)

    result = asyncio.run(client.get_ai_service_history("server-id", "next-token"))

    assert result == {"items": []}
    call = session.calls[0]
    assert call["url"] == "https://api.x-sense-iot.com/app"
    assert call["json"]["bizCode"] == "701008"
    assert call["json"]["serverId"] == "server-id"
    assert call["json"]["nextToken"] == "next-token"


def test_camera_event_history_uses_addx_library_record_path():
    session = AsyncFakeSession(
        [
            AsyncFakeResponse(
                payload={
                    "result": 0,
                    "data": {"records": [{"serialNumber": "CAM123"}]},
                }
            )
        ]
    )
    client = AsyncXSense(session)
    client._addx_session = {
        "nodeType": "US",
        "token": "addx-token",
        "countryNo": "1",
        "language": "en",
    }

    result = asyncio.run(
        client.get_camera_event_history(
            ["CAM123"],
            1710000000000,
            1710003600000,
            start=20,
            limit=40,
        )
    )

    assert result == {"records": [{"serialNumber": "CAM123"}]}
    call = session.calls[0]
    assert call["url"] == "https://api-us.vicohome.io/library/newselectlibrary"
    assert call["headers"] == {
        "Authorization": "addx-token",
        "Content-Type": "application/json",
    }
    assert call["json"]["serialNumber"] == ["CAM123"]
    assert call["json"]["startTimestamp"] == 1710000000000
    assert call["json"]["endTimestamp"] == 1710003600000
    assert call["json"]["from"] == 20
    assert call["json"]["to"] == 40
    assert call["json"]["tags"] == []
    assert call["json"]["marked"] == 0


class RetryingAddxClient(AsyncXSense):
    def __init__(self, session):
        super().__init__(session)
        self._addx_session = {
            "nodeType": "US",
            "token": "expired-addx-token",
            "countryNo": "1",
            "language": "en",
        }
        self.registers = 0

    async def register_ipc(self):
        self.registers += 1
        return {
            "nodeType": "US",
            "token": f"fresh-addx-token-{self.registers}",
            "countryNo": "1",
            "language": "en",
        }


def test_addx_call_re_registers_ipc_and_retries_once_after_auth_failure():
    session = AsyncFakeSession(
        [
            AsyncFakeResponse(status=401, payload={"msg": "expired"}),
            AsyncFakeResponse(payload={"result": 0, "data": {"ok": True}}),
        ]
    )
    client = RetryingAddxClient(session)

    result = asyncio.run(client.addx_call("/device/list", serialNumber="CAM123"))

    assert result == {"ok": True}
    assert client.registers == 1
    assert len(session.calls) == 2
    assert session.calls[0]["headers"]["Authorization"] == "expired-addx-token"
    assert session.calls[1]["headers"]["Authorization"] == "fresh-addx-token-1"


def test_addx_call_does_not_retry_twice_after_auth_failure():
    session = AsyncFakeSession(
        [
            AsyncFakeResponse(status=401, payload={"msg": "expired"}),
            AsyncFakeResponse(status=403, payload={"message": "still expired"}),
        ]
    )
    client = RetryingAddxClient(session)

    with pytest.raises(APIFailure, match="still expired"):
        asyncio.run(client.addx_call("/device/list", serialNumber="CAM123"))

    assert client.registers == 1
    assert len(session.calls) == 2


class FakeCamera:
    def __init__(self, data=None):
        self.sn = "CAM123"
        self.data = dict(data or {})

    def set_data(self, values):
        self.data.update(values)


class StubAddxClient(AsyncXSense):
    def __init__(self, responses):
        super().__init__(session=AsyncFakeSession())
        self.responses = list(responses)
        self.addx_calls = []

    async def addx_call(self, endpoint: str, **kwargs):
        self.addx_calls.append((endpoint, kwargs))
        if self.responses:
            return self.responses.pop(0)
        return {}


def test_camera_live_resolution_prefers_saved_supported_resolution():
    from xsense.async_xsense import camera_live_resolution

    camera = FakeCamera(
        {
            "supportedRecordingResolutions": ["720P", "1080P"],
            "liveResolution": "VIDEO_SIZE_1080P",
        }
    )

    assert camera_live_resolution(camera) == "1920x1080"


def test_camera_live_resolution_falls_back_to_first_supported_resolution():
    from xsense.async_xsense import camera_live_resolution

    camera = FakeCamera(
        {
            "deviceSupportResolution": ["720P", "1080P"],
            "liveResolution": "4K",
        }
    )

    assert camera_live_resolution(camera) == "1280x720"


def test_camera_stream_protocol_helpers_detect_native_and_webrtc_modes():
    from xsense.async_xsense import (
        camera_online,
        camera_stream_protocol,
        is_native_stream_camera,
        is_webrtc_camera,
        stream_source_protocol,
    )

    rtsp_camera = FakeCamera({"streamProtocol": "RTSP"})
    rtsp_camera.online = True
    webrtc_camera = FakeCamera({"streamProtocol": "webrtc"})
    unknown_camera = FakeCamera({})
    fallback_online_camera = FakeCamera({"online": 1})

    assert camera_online(rtsp_camera) is True
    assert camera_online(fallback_online_camera) is True
    assert camera_stream_protocol(rtsp_camera) == "rtsp"
    assert stream_source_protocol("RTSP://camera/live") == "rtsp"
    assert stream_source_protocol("not-a-url") is None
    assert is_native_stream_camera(rtsp_camera) is True
    assert is_webrtc_camera(rtsp_camera) is False
    assert is_native_stream_camera(webrtc_camera) is False
    assert is_webrtc_camera(webrtc_camera) is True
    assert is_native_stream_camera(unknown_camera) is False
    assert is_webrtc_camera(unknown_camera) is True


def test_get_camera_webrtc_ticket_reuses_valid_cache():
    expires = int(datetime.now().timestamp() * 1000) + 60000
    ticket = {"ticket": "cached", "expirationTime": expires}
    camera = FakeCamera({"cameraWebrtcTicket": ticket})
    client = StubAddxClient([{"ticket": "fresh"}])

    result = asyncio.run(client.get_camera_webrtc_ticket(camera))

    assert result == ticket
    assert client.addx_calls == []


def test_get_camera_webrtc_ticket_fetches_missing_expiration():
    camera = FakeCamera({"cameraWebrtcTicket": {"ticket": "stale"}})
    client = StubAddxClient([{"ticket": "fresh", "expirationTime": "9999999999999"}])

    result = asyncio.run(client.get_camera_webrtc_ticket(camera))

    assert result == {"ticket": "fresh", "expirationTime": "9999999999999"}
    assert camera.data["cameraWebrtcTicket"] == result
    assert client.addx_calls == [
        (
            "/device/getWebrtcTicket",
            {"serialNumber": "CAM123", "verifyDormancyStatus": True},
        )
    ]


def test_start_camera_live_uses_direct_stream_source_endpoint():
    camera = FakeCamera({"supportedRecordingResolutions": ["1080P"]})
    client = StubAddxClient(
        [
            {
                "liveUrl": "rtsp://camera/live",
                "audioUrl": "rtsp://camera/audio",
                "liveId": "live-id",
            }
        ]
    )

    result = asyncio.run(client.start_camera_live(camera))

    assert result == "rtsp://camera/live"
    assert camera.data["cameraLiveUrl"] == "rtsp://camera/live"
    assert camera.data["cameraAudioUrl"] == "rtsp://camera/audio"
    assert camera.data["cameraLiveId"] == "live-id"
    assert camera.data["cameraLiveProtocol"] == "rtsp"
    assert client.addx_calls == [
        (
            "/device/newstartlive",
            {"serialNumber": "CAM123", "liveResolution": "1920x1080"},
        )
    ]


def test_start_camera_live_reuses_recent_url():
    camera = FakeCamera(
        {
            "cameraLiveStartedAt": datetime.now(),
            "cameraLiveUrl": "rtmp://camera/live",
        }
    )
    client = StubAddxClient([{"liveUrl": "rtsp://camera/new"}])

    result = asyncio.run(client.start_camera_live(camera))

    assert result == "rtmp://camera/live"
    assert client.addx_calls == []


def test_stop_camera_live_clears_live_and_webrtc_ticket_state():
    camera = FakeCamera(
        {
            "cameraAudioUrl": "rtsp://camera/audio",
            "cameraLiveId": "live-id",
            "cameraLiveStartedAt": datetime.now(),
            "cameraLiveUrl": "rtsp://camera/live",
            "cameraLiveProtocol": "rtsp",
            "cameraWebrtcTicket": {"ticket": "ticket"},
        }
    )
    client = StubAddxClient([{}])

    asyncio.run(client.stop_camera_live(camera))

    assert client.addx_calls == [
        ("/device/stoplive", {"serialNumber": "CAM123"})
    ]
    assert camera.data["cameraAudioUrl"] is None
    assert camera.data["cameraLiveId"] is None
    assert camera.data["cameraLiveStartedAt"] is None
    assert camera.data["cameraLiveUrl"] is None
    assert camera.data["cameraLiveProtocol"] is None
    assert camera.data["cameraWebrtcTicket"] is None


def test_camera_keepalive_and_wake_use_app_endpoints():
    camera = FakeCamera()
    client = StubAddxClient([{}, {}])

    asyncio.run(client.keep_camera_live_alive(camera))
    asyncio.run(client.wake_camera(camera))

    assert client.addx_calls == [
        ("/device/keepalive", {"serialNumber": "CAM123", "seconds": 30}),
        ("/device/wakeupDevice", {"serialNumber": "CAM123"}),
    ]
