import base64
import hashlib
import hmac
import json


class XSenseBase:
    API = 'https://api.x-sense-iot.com'
    VERSION = "v1.17.2_20240115"
    APPCODE = "1172"
    CLIENTYPE = "1"

    username = None
    clientid = None
    clientsecret = None
    userpool = None
    region = None

    access_token = None
    id_token = None
    refresh_token = None
    access_key = None
    secret_access_key = None
    session_token = None
    token_expiration = None

    signer = None

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

    def generate_hash(self, data):
        return base64.b64encode(
            hmac.new(
                self.clientsecret,
                bytes(data, 'utf-8'),
                digestmod=hashlib.sha256
            ).digest()
        ).decode()
