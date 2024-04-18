Python-xsense
=============

Python-xsense is a small library to interact with the API of XSense Home
Security. It allows to retrieve the status of various devices and the
basestation.

Example sync usage
------------------

::

   >>> from xsense import XSense
   >>> from xsense.utils import dump_environment
   >>> api = XSense()
   >>> api.init()
   >>> api.login(username, password)
   >>> api.load_all()
   >>> for _, h in api.houses.items():
   >>>     for _, s in h.stations.items():
   >>>         api.get_state(s)
   >>> dump_environment(api)

Example async usage
-------------------

::

   >>> import asyncio
   >>> from xsense import AsyncXSense
   >>> from xsense.utils import dump_environment
   >>>
   >>> async def run(username: str, password: str):
   >>>     api = AsyncXSense()
   >>>     await api.init()
   >>>     await api.login(username, password)
   >>>     for _, h in api.houses.items():
   >>>         for _, s in h.stations.items():
   >>>             await api.get_state(s)
   >>>     dump_environment(api)
   >>>
   >>> asyncio.run(run(username, password))

Development
-----------

This library is in an early development stage and created primarily to
make an integration for home assistant.
