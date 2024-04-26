import asyncio
from datetime import datetime
import json

import aiohttp

from xsense.aws_signer import AWSSigner
from xsense.base import XSenseBase
from xsense.exceptions import SessionExpired, APIFailure
from xsense.house import House
from xsense.station import Station


class AsyncXSense(XSenseBase):
    async def api_call(self, code, unauth=False, **kwargs):
        data = {
            **kwargs
        }

        if unauth:
            headers = None
            mac = 'abcdefg'
        else:
            if self._access_token_expiring():
                await self.refresh()
            headers = {'Authorization': self.access_token}
            mac = self._calculate_mac(data)

        async with aiohttp.ClientSession() as session:
            async with session.post(
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
            ) as response:
                self._lastres = response

                data = await response.json()

                if response.status >= 400:
                    message = data.get('message') or 'unknown error'
                    raise APIFailure(f'API failure: {response.status}/{message}')

                if 'reCode' not in data:
                    raise APIFailure('API failure: Cannot understand response')

                if data['reCode'] != 200:
                    errCode = data.get('errCode', 0)
                    if errCode in ('10000008', '10000020'):
                        raise SessionExpired(data.get('reMsg'))
                    raise APIFailure(
                        f"Request for code {code} failed with error {errCode}/{data['reCode']} {data.get('reMsg')}"
                    )
                return data['reData']

    async def get_thing(self, station: Station, page: str):
        if self._aws_token_expiring():
            await self.load_aws()

        url, headers = self._thing_request(station, page)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers
            ) as response:
                self._lastres = response
                return await response.json()

    async def login(self, username, password):
        await asyncio.get_event_loop().run_in_executor(None, self.sync_login, username, password)
        await self.load_aws()

    async def refresh(self):
        url, data, headers = self._refresh_request()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=data, headers=headers
            ) as response:
                self._lastres = response
                text = await response.text()
                data = json.loads(text)

                if response.status == 400:
                    raise SessionExpired(data.get('message', 'token refresh failed'))

                self._parse_refresh_result(data.get('AuthenticationResult', {}))

    async def init(self):
        await self.get_client_info()

    async def load_aws(self):
        await self.get_aws_tokens()
        self.signer = AWSSigner(self.aws_access_key, self.aws_secret_access_key, self.aws_session_token)

    async def load_all(self):
        result = {}
        for i in await self.get_houses():
            h = House(
                i['houseId'],
                i['houseName'],
                i['houseRegion'],
                i['mqttRegion'],
                i['mqttServer']
            )
            result[i['houseId']] = h

            if rooms := await self.get_rooms(h.house_id):
                h.set_rooms(rooms)

            if station := await self.get_stations(h.house_id):
                h.set_stations(station)
        self.houses = result

    async def get_client_info(self):
        data = await self.api_call("101001", unauth=True)
        self.clientid = data['clientId']
        self.clientsecret = self._decode_secret(data['clientSecret'])
        self.region = data['cgtRegion']
        self.userpool = data['userPoolId']

    async def get_aws_tokens(self):
        data = await self.api_call("101003", userName=self.username)
        self.aws_access_key = data['accessKeyId']
        self.aws_secret_access_key = data['secretAccessKey']
        self.aws_session_token = data['sessionToken']
        self.aws_access_expiry = datetime.strptime(data['expiration'], "%Y-%m-%d %H:%M:%S%z")

    async def get_houses(self):
        params = {
            'utctimestamp': "0"
        }
        return await self.api_call("102007", **params)

    async def get_rooms(self, houseId: str):
        params = {
            'houseId': houseId,
            'utctimestamp': "0"
        }
        return await self.api_call("102008", **params)

    async def get_stations(self, houseId: str):
        params = {
            'houseId': houseId,
            'utctimestamp': "0"
        }
        return await self.api_call("103007", **params)

    async def get_station_state(self, station: Station):
        res = await self.get_thing(station, f'2nd_info_{station.sn}')

        if 'reported' in res.get('state', {}):
            station.set_data(res['state']['reported'])
        else:
            raise APIFailure(f'Unable to retrieve station data: {self._lastres.status}/{self._lastres.text()}')

    async def get_state(self, station: Station):
        res = await self.get_thing(station, '2nd_mainpage')

        if 'reported' in res.get('state', {}):
            self._parse_get_state(station, res['state']['reported'])
        else:
            raise APIFailure(f'Unable to retrieve station data: {self._lastres.status}/{self._lastres.text()}')
