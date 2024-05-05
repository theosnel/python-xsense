from xsense import XSense
from xsense.exceptions import APIFailure

from xsense.utils import dump_environment, get_credentials

api = XSense()
api.init()

username, password = get_credentials()
api.login(username, password)
api.load_all()
for _, h in api.houses.items():
    api.get_house_state(h)
    for _, s in h.stations.items():
        try:
            api.get_station_state(s)
            api.get_state(s)
        except APIFailure as e:
            print(f'ERROR: {e}')

dump_environment(api)
