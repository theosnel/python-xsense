from xsense import XSense

from xsense.utils import dump_environment, get_credentials

api = XSense()
api.init()

username, password = get_credentials()
api.login(username, password)
api.load_all()
for _, h in api.houses.items():
    for _, s in h.stations.items():
        api.get_state(s)

dump_environment(api)
