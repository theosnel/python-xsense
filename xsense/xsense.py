from datetime import datetime, timedelta

import requests

from xsense.aws_signer import AWSSigner
from xsense.base import XSenseBase
from xsense.exceptions import APIFailure, SessionExpired
from xsense.house import House
from xsense.station import Station


class XSense(XSenseBase):
    def api_call(self, code, unauth=False, **kwargs):
        data = {
            **kwargs
        }

        if unauth:
            headers = None
            mac = 'abcdefg'
        else:
            if self._access_token_expiring():
                self.refresh()
            headers = {'Authorization': self.access_token}
            mac = self._calculate_mac(data)

        res = requests.post(
            f'{self.API}/app',
            json={
                **data,
                "clientType": self.CLIENTYPE,
                "mac": mac,
                "appVersion": self.VERSION,
                "bizCode": code,
                "appCode": self.APPCODE,
            },
            headers=headers
        )
        self._lastres = res

        data = res.json()
        if res.status_code >= 400:
            message = data.get('message') or 'unknown error'
            raise APIFailure(f'API failure: {res.status_code}/{message}')

        if 'reCode' not in data:
            raise APIFailure('API failure: Cannot understand response')

        if data['reCode'] != 200:
            errCode = data.get('errCode', 0)
            if errCode in ('10000008', '10000020'):
                raise SessionExpired(data.get('reMsg'))
            raise APIFailure(f"Request for code {code} failed with error {errCode}/{data['reCode']} {data.get('reMsg')}")

        return data['reData']

    def get_thing(self, station: Station, page: str):
        if self._aws_token_expiring():
            self.load_aws()

        url, headers = self._thing_request(station, page)

        return requests.get(url, headers=headers).json()

    def login(self, username, password):
        self.sync_login(username, password)
        self.load_aws()

    def refresh(self):
        url, data, headers = self._refresh_request()

        res = requests.post(
            url,
            json=data,
            headers=headers
        )
        self._lastres = res
        data = res.json()

        if res.status_code == 400:
            raise SessionExpired(data.get('message', 'token refresh failed'))

        self._parse_refresh_result(data.get('AuthenticationResult', {}))

    def init(self):
        self.get_client_info()

    def load_aws(self):
        self.get_aws_tokens()
        self.signer = AWSSigner(self.aws_access_key, self.aws_secret_access_key, self.aws_session_token)

    def load_all(self):
        result = {}
        for i in self.get_houses():
            h = House(
                i['houseId'],
                i['houseName'],
                i['houseRegion'],
                i['mqttRegion'],
                i['mqttServer']
            )
            result[i['houseId']] = h

            if rooms := self.get_rooms(h.house_id):
                h.set_rooms(rooms)

            if station := self.get_stations(h.house_id):
                h.set_stations(station)
        self.houses = result

    def get_client_info(self):
        data = self.api_call("101001", unauth=True)
        self.clientid = data['clientId']
        self.clientsecret = self._decode_secret(data['clientSecret'])
        self.region = data['cgtRegion']
        self.userpool = data['userPoolId']

    def get_aws_tokens(self):
        data = self.api_call("101003", userName=self.username)
        self.aws_access_key = data['accessKeyId']
        self.aws_secret_access_key = data['secretAccessKey']
        self.aws_session_token = data['sessionToken']
        self.aws_access_expiry = datetime.strptime(data['expiration'], "%Y-%m-%d %H:%M:%S%z")

    def get_houses(self):
        params = {
            'utctimestamp': "0"
        }
        return self.api_call("102007", **params)

    def get_rooms(self, houseId: str):
        params = {
            'houseId': houseId,
            'utctimestamp': "0"
        }
        return self.api_call("102008", **params)

    def get_stations(self, houseId: str):
        params = {
            'houseId': houseId,
            'utctimestamp': "0"
        }
        return self.api_call("103007", **params)

    def get_station_state(self, station: Station):
        res = self.get_thing(station, f'2nd_info_{station.sn}')

        if 'reported' in res.get('state', {}):
            station.set_data(res['state']['reported'])
        else:
            raise APIFailure(f'Unable to retrieve station data: {self._lastres.status_code}/{self._lastres.text}')

    def get_state(self, station: Station):
        res = self.get_thing(station, '2nd_mainpage')

        if 'reported' in res.get('state', {}):
            self._parse_get_state(station, res['state']['reported'])
        else:
            raise APIFailure(f'Unable to retrieve station data: {self._lastres.status_code}/{self._lastres.text}')
