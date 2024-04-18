Python-xsense
=============


Python-xsense is a small library to interact with the API of XSense Home Security.
It allows to retrieve the status of various devices and the basestation.


Example sync usage
------------------

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

    >>> api = AsyncXSense()
    >>> await api.init()
    >>> await api.login(username, password)
    >>> for _, h in api.houses.items():
    >>>     for _, s in h.stations.items():
    >>>         await api.get_state(s)
    >>> dump_environment(api)


Development
-----------
This library is in an early development stage and created primarily to make an integration for home assistant.
