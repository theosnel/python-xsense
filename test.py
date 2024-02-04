from pprint import pprint
from xsense import XSense


username = ''
passwd = ''

api = XSense()
api.init()
api.login(username, passwd)

houses = api.get_houses()
pprint(houses)

for h in houses:
    rooms = api.get_rooms(h['houseId'])
    pprint(rooms)
