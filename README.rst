Python-xsense
=============

Python-xsense is a client library for X-Sense cloud accounts, AWS IoT
shadows, MQTT updates, ADDX/VicoHome camera APIs, recording metadata and local
SD playback controls, WebRTC signaling, and supported device actions/settings.

Supported Python versions are 3.10 through 3.14.

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

The established synchronous ``XSense`` client remains available for existing
consumers alongside ``AsyncXSense``.

Synchronous compatibility
-------------------------

::

   >>> from xsense import XSense
   >>> with XSense() as api:
   ...     api.init()
   ...     api.login(username, password)
   ...     api.load_all()

Reusable helpers
----------------

The main async client lives in ``xsense.AsyncXSense``. It exposes the current
X-Sense app API request shape, Cognito session refresh, AWS IoT shadow
reads/writes, ADDX/VicoHome camera discovery, camera thumbnails, WebRTC tickets,
and signal-relay helpers, plus supported device actions/settings.

Pure parsing helpers live in separate modules:

* ``xsense.event_parser`` parses MQTT, camera history, AI detection, presence,
  and self-test event payloads.
* ``xsense.mqtt_helper`` handles X-Sense MQTT connection setup, topics,
  subscription helpers, payload parsing, and publish helpers.
* ``xsense.webrtc_signal`` parses ADDX WebRTC tickets and builds/parses the
  signal-server SDP and ICE payloads.

Client surface
--------------

The library provides the reusable X-Sense client and protocol surface used by
the Home Assistant integration:

* authentication, token refresh, app request signing, and AWS credential loading
* X-Sense ``/app`` calls and AWS IoT shadow reads/writes
* house, station, device, camera, and entity mapping/normalization
* MQTT connection helpers, shadow/presence topics, and payload parsing
* ADDX/VicoHome camera discovery, metadata/config merging, thumbnails, history,
  AI history, WebRTC tickets, and signal-relay helpers
* reusable device actions and settings writes for supported device data

Maintenance
-----------

This library is maintained as a shared upstream client for the X-Sense Home
Security integration and other Python consumers.
