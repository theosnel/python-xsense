import asyncio

from xsense.async_xsense import AsyncXSense, _camera_data
from xsense.entity_map import EntityType
from xsense.house import House
from xsense.station import Station


class FakeSigner:
    def presign_url(self, *args):
        return "wss://mqtt.example/mqtt?sig=abc"


class CameraClient(AsyncXSense):
    def __init__(self, responses):
        super().__init__(session=None)
        self.responses = list(responses)
        self.calls = []

    async def addx_call(self, endpoint: str, **kwargs):
        self.calls.append((endpoint, kwargs))
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return None


class ThumbnailResponse:
    def __init__(self, status=200, content=b"jpeg-bytes"):
        self.status = status
        self.content = content

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def read(self):
        return self.content


class ThumbnailSession:
    closed = False

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        return self.responses.pop(0)


def _house(house_id="house-id"):
    house = House(FakeSigner(), house_id, "Home", "US", "us-east-1", "mqtt.example")
    house.set_rooms({"houseRooms": {}, "roomSort": []})
    house.set_stations({"stationSort": [], "stations": []})
    return house


def test_camera_data_normalizes_addx_support_and_status_fields():
    data = _camera_data(
        {
            "displayModelNo": "SSC0A",
            "online": 1,
            "awake": 0,
            "deviceStatus": "2",
            "statusCode": "3",
            "isCharging": "1",
            "thumbImgUrl": "https://example/thumb.jpg",
            "sdCard": {"formatStatus": 0, "total": "128", "used": "64"},
            "deviceModel": {
                "modelName": "SSC0A",
                "streamProtocol": "webrtc",
                "canStandby": 1,
                "whiteLight": 0,
            },
            "deviceSupport": {
                "supportWebrtc": 1,
                "supportLiveAudioToggle": 1,
                "supportRecordingAudioToggle": 0,
                "deviceDormancySupport": 1,
                "deviceSupportResolution": ["1080P"],
            },
        }
    )

    assert data["cameraModel"] == "SSC0A"
    assert data["online"] == 1
    assert data["awake"] == 0
    assert data["deviceStatus"] == "2"
    assert data["cameraStatusCode"] == "3"
    assert data["isCharging"] is True
    assert data["thumbImgUrl"] == "https://example/thumb.jpg"
    assert data["streamProtocol"] == "webrtc"
    assert data["supportWebrtc"] is True
    assert data["supportLiveAudio"] is True
    assert data["supportRecordingAudio"] is False
    assert data["supportBattery"] is True
    assert data["supportLight"] is False
    assert data["supportSdCard"] is True
    assert data["supportSleep"] is True
    assert data["supportedRecordingResolutions"] == ["1080P"]


def test_update_camera_data_creates_camera_from_addx_device_list():
    client = CameraClient(
        [
            {
                "list": [
                    {
                        "serialNumber": "CAM123",
                        "deviceName": "Driveway Camera",
                        "houseId": "house-id",
                        "displayModelNo": "SSC0A",
                        "online": 1,
                        "deviceSupport": {"supportWebrtc": 1},
                    }
                ]
            },
            {},
            {},
            None,
        ]
    )
    house = _house()
    client.houses = {house.house_id: house}

    asyncio.run(client.update_camera_data())

    camera = house.stations["CAM123"]
    assert camera.name == "Driveway Camera"
    assert camera.sn == "CAM123"
    assert camera.type == "SSC0A"
    assert camera.entity_type == EntityType.CAMERA
    assert camera.online is True
    assert camera.data["supportWebrtc"] is True
    assert client.calls[0] == ("/device/listuserdevices", {})


def test_update_camera_data_updates_existing_camera_metadata():
    house = _house()
    station = Station(
        house,
        stationId="camera-id",
        stationSn="CAM123",
        stationName="Old Name",
        category="SSC0B",
        deviceType="SSC0B",
        devices=[],
    )
    station.entity_type = EntityType.CAMERA
    station.set_devices({"devices": []})
    house.stations[station.entity_id] = station

    client = CameraClient(
        [
            {
                "list": [
                    {
                        "serialNumber": "cam-123",
                        "deviceName": "Front Camera",
                        "displayModelNo": "SSC0A",
                        "online": 0,
                    }
                ]
            },
            {},
            {},
            None,
        ]
    )
    client.houses = {house.house_id: house}

    asyncio.run(client.update_camera_data())

    assert station.name == "Front Camera"
    assert station.type == "SSC0A"
    assert station.online is False


def test_update_camera_data_does_not_place_unknown_camera_in_multi_house_account():
    client = CameraClient(
        [
            {
                "list": [
                    {
                        "serialNumber": "CAM123",
                        "deviceName": "Floating Camera",
                        "displayModelNo": "SSC0A",
                    }
                ]
            }
        ]
    )
    first = _house("first")
    second = _house("second")
    client.houses = {first.house_id: first, second.house_id: second}

    asyncio.run(client.update_camera_data())

    assert first.stations == {}
    assert second.stations == {}


def test_get_camera_thumbnail_fetches_thumbnail_url_bytes():
    session = ThumbnailSession([ThumbnailResponse(content=b"thumb")])
    client = AsyncXSense(session)
    camera = Station(
        _house(),
        stationId="camera-id",
        stationSn="CAM123",
        stationName="Camera",
        category="SSC0A",
        deviceType="SSC0A",
        devices=[],
    )
    camera.set_data({"thumbImgUrl": "https://example/thumb.jpg"})

    result = asyncio.run(client.get_camera_thumbnail(camera))

    assert result == b"thumb"
    assert session.calls == ["https://example/thumb.jpg"]


def test_get_camera_thumbnail_returns_none_without_url_or_on_failure():
    session = ThumbnailSession([ThumbnailResponse(status=404, content=b"missing")])
    client = AsyncXSense(session)
    camera = Station(
        _house(),
        stationId="camera-id",
        stationSn="CAM123",
        stationName="Camera",
        category="SSC0A",
        deviceType="SSC0A",
        devices=[],
    )

    assert asyncio.run(client.get_camera_thumbnail(camera)) is None

    camera.set_data({"thumbImgUrl": "https://example/missing.jpg"})

    assert asyncio.run(client.get_camera_thumbnail(camera)) is None
    assert session.calls == ["https://example/missing.jpg"]
