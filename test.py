from contextlib import suppress

from xsense import XSense
from xsense.exceptions import APIFailure, NotFoundError

from xsense.utils import dump_environment, get_credentials

api = XSense()
api.init()

username, password = get_credentials()
api.login(username, password)
api.load_all()
for _, h in api.houses.items():
    try:
        api.get_house_state(h)
    except NotFoundError:
        print(f'could not retrieve status for {h.name}')
    for _, s in h.stations.items():
        try:
            api.get_station_state(s)
            api.get_state(s)

            for _, d in s.devices.items():
                with suppress(NotFoundError):
                    res = api.get_device_state(s, d)

        except APIFailure as e:
            print(f'ERROR: {e}')

dump_environment(api)
