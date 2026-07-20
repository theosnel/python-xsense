Python-xsense
=============

Python-xsense is an async client library for X-Sense cloud accounts,
AWS IoT shadows, MQTT updates, ADDX/VicoHome camera APIs, camera history,
live-view helpers, and supported device actions/settings.

Supported Python versions are 3.10 through 3.14. Home Assistant currently runs
on a newer Python, but the library keeps the lower floor for scripts and other
async Python consumers when the test matrix proves compatibility.

This package contains reusable Python client logic only. Home Assistant
entity descriptions, icons, translations, blueprints, platform setup, and
registry cleanup belong in the Home Assistant integration.

Client usage
------------

::

   >>> import asyncio
   >>> from xsense import AsyncXSense
   >>> from xsense.utils import dump_environment
   >>>
   >>> async def run(username: str, password: str):
   >>>     async with AsyncXSense() as api:
   >>>         await api.init()
   >>>         await api.login(username, password)
   >>>         await api.load_all()
   >>>         for house in api.houses.values():
   >>>             for station in house.stations.values():
   >>>                 await api.get_state(station)
   >>>         dump_environment(api)
   >>>
   >>> asyncio.run(run(username, password))

Reusable helpers
----------------

The main async client lives in ``xsense.AsyncXSense``. It exposes the current
X-Sense app API request shape, Cognito session refresh, AWS IoT shadow
reads/writes, ADDX/VicoHome camera discovery, camera thumbnail and live-view
helpers, and supported device actions/settings.

Pure parsing helpers live in separate modules:

* ``xsense.event_parser`` parses MQTT, camera history, AI detection, presence,
  and self-test event payloads.
* ``xsense.mqtt_helper`` handles X-Sense MQTT connection setup, topics,
  subscription helpers, payload parsing, and publish helpers.
* ``xsense.webrtc_signal`` parses ADDX WebRTC tickets and builds/parses the
  signal-server SDP and ICE payloads.

Migration surface
-----------------

The library is intended to carry the reusable surface currently embedded under
the Home Assistant integration's ``custom_components/xsense/api`` package:

* authentication, token refresh, app request signing, and AWS credential loading
* X-Sense ``/app`` calls and AWS IoT shadow reads/writes
* house, station, device, camera, and entity mapping/normalization
* MQTT connection helpers, shadow/presence topics, and payload parsing
* ADDX/VicoHome camera discovery, metadata/config merging, thumbnails, history,
  AI history, WebRTC tickets, and live-view helpers
* reusable device actions and settings writes for supported device data

Development
-----------

This library is in an early development stage. It is maintained as a
shared upstream client for integrations and other async Python consumers.
