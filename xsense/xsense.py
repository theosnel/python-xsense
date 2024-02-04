from pprint import pprint

import json
import requests
import base64
import hmac
import hashlib
import boto3
from botocore.exceptions import ClientError
from pycognito import AWSSRP


class XSense:
    API = 'https://api.x-sense-iot.com'
    VERSION = "v1.17.2_20240115"
    APPCODE = "1172"
    CLIENTYPE = "2"

    username = None
    clientid = None
    clientsecret = None
    userpool = None
    region = None

    access_token = None
    id_token = None
    refresh_token = None

    _lastres = None

    def _decode_secret(self, encoded):
        value = base64.b64decode(encoded)
        return value[4:-1]

    def _calculate_mac(self, data):
        values = []
        if data:
            for key in data:
                value = data[key]
                if isinstance(value, list):
                    if value and isinstance(value[0], str):
                        values.extend(value)
                    else:
                        values.append(json.dumps(value))
                elif isinstance(value, dict):
                    values.append(json.dumps(value, separators=(',', ':')))
                else:
                    values.append(str(value))

        concatenated_string = ''.join(values)
        mac_data = concatenated_string.encode('utf-8') + self.clientsecret
        return hashlib.md5(mac_data).hexdigest()

    def api_call(self, code, unauth=False, **kwargs):
        data = {
            **kwargs
        }

        if unauth:
           headers = None
           mac='abcdefg'
        else:
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
        if data['reCode'] != 200:
            raise RuntimeError(f"Request for code {code} failed with error {data['reCode']} {data.get('reMsg')}")
        return data['reData']

    def generate_hash(self, data):
        return base64.b64encode(
            hmac.new(
                self.clientsecret,
                bytes(data, 'utf-8'),
                digestmod=hashlib.sha256
            ).digest()
        ).decode()

    def init(self):
        self.get_client_info()

    def login(self, username, password):
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

    def get_client_info(self):
        data = self.api_call("101001", unauth=True)
        self.clientid = data['clientId']
        self.clientsecret = self._decode_secret(data['clientSecret'])
        self.region = data['cgtRegion']
        self.userpool = data['userPoolId']

        # pprint(data)

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
