import asyncio
import aiohttp

import boto3
from botocore.exceptions import ClientError
from pycognito import AWSSRP

from xsense.aws_signer import AWSSigner
from xsense.base import XSenseBase
from xsense.house import House
from xsense.mapping import map_values
from xsense.station import Station


class AsyncXSense(XSenseBase):
    async def api_call(self, code, unauth=False, **kwargs):
        data = {
            **kwargs
        }

        if unauth:
           headers = None
           mac='abcdefg'
        else:
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
                if data['reCode'] != 200:
                    raise RuntimeError(f"Request for code {code} failed with error {data['reCode']} {data.get('reMsg')}")
                return data['reData']

    async def get_thing(self, station: Station, page: str):
        headers = {
            'Content-Type': 'application/x-amz-json-1.0',
            'User-Agent': 'aws-sdk-iOS/2.26.5 iOS/17.3 nl_NL',
            'X-Amz-Security-Token': self.session_token
        }

        host = f'{station.house.mqtt_region}.x-sense-iot.com'
        uri = f'/things/SBS50{station.sn}/shadow?name={page}'

        url = f'https://{host}{uri}'

        signed = self.signer.sign_headers('GET', url, station.house.mqtt_region, headers, None)
        headers |= signed
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers
            ) as response:
                self._lastres = response
                return await response.json()

    def sync_login(self, username, password):
        self.username = username
        session = boto3.Session()
        cognito = session.client('cognito-idp', region_name=self.region)

        aws_srp = AWSSRP(
            username=username,
            password=password,
            pool_id=self.userpool,
            client_id=self.clientid,
            client=cognito
        )

        auth_params = aws_srp.get_auth_params()
        auth_params['SECRET_HASH'] = self.generate_hash(username + self.clientid)

        try:
            response = cognito.initiate_auth(
                ClientId=self.clientid,
                AuthFlow='USER_SRP_AUTH',
                AuthParameters=auth_params
            )
        except ClientError as e:
            raise RuntimeError(f'Cannot login, initiate_auth failed: {e}') from e

        userid = response['ChallengeParameters']['USERNAME']

        challenge_response = aws_srp.process_challenge(response["ChallengeParameters"], auth_params)

        challenge_response['SECRET_HASH'] = self.generate_hash(userid + self.clientid)

        try:
            response = cognito.respond_to_auth_challenge(
                ClientId=self.clientid,
                ChallengeName='PASSWORD_VERIFIER',
                ChallengeResponses=challenge_response
            )

            self.access_token = response['AuthenticationResult']['AccessToken']
            self.id_token = response['AuthenticationResult']['IdToken']
            self.refresh_token = response['AuthenticationResult']['RefreshToken']

        except ClientError as e:
            raise RuntimeError(f'Cannot login, respond_to_auth failed: {e}') from e

    async def login(self, username, password):
        await asyncio.get_event_loop().run_in_executor(None, self.sync_login, username, password)
        await self.load_env()

    async def init(self):
        await self.get_client_info()

    async def load_env(self):
        await self.get_access_tokens()

        self.signer = AWSSigner(self.access_key, self.secret_access_key, self.session_token)

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

    async def get_access_tokens(self):
        data = await self.api_call("101003", userName=self.username)
        self.access_key = data['accessKeyId']
        self.secret_access_key = data['secretAccessKey']
        self.session_token = data['sessionToken']
        self.token_expiration = data['expiration']

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

    async def get_state(self, station: Station):
        res = await self.get_thing(station, '2nd_mainpage')

        for sn, i in res['state']['reported']['devs'].items():
            dev = station.get_device_by_sn(sn)
            dev.set_status(i)
