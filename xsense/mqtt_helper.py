"""A helper class to setup the MQTT client, generate connection urls and parse messages"""
import uuid
import ssl
from datetime import datetime, timedelta
from typing import Dict

from paho.mqtt import client as mqtt_client

from xsense.aws_signer import AWSSigner


URL_MAX_AGE = 5
USERNAME = '?SDK=iOS&Version=2.26.5'
FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = 60


class MQTTHelper:
    _sig_age = None
    active: bool
    _last_update = None
    _update_callback = None
    _mqtt_path = None

    def _get_path(self):
        if (
            not self._mqtt_path or
            not self._sig_age or
            datetime.now() - self._sig_age > timedelta(minutes=URL_MAX_AGE)
        ):
            signed = self.signer.presign_url(f'wss://{self.house.mqtt_server}/mqtt', self.house.mqtt_region)
            url_parts = signed.split("/")
            self._mqtt_path = "/" + "/".join(url_parts[3:])
            _sig_age = datetime.now()

        return self._mqtt_path

    def __init__(self, signer: AWSSigner, house: 'House'):
        self.signer = signer
        self.house = house

        self.client = mqtt_client.Client(
            client_id=str(uuid.uuid4()),
            reconnect_on_failure=False,
            transport='websockets'
        )

        self.client.username_pw_set(USERNAME, '')
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        ssl_context.verify_mode = ssl.CERT_NONE
        self.client.tls_set_context(ssl_context)

    def prepare_connect(self):
        def fix_websocket_headers(headers: Dict) -> Dict:
            """
            Remove port-number from Host and origin, XSense doesn't accept signing with it
            """

            if 'Host' in headers:
                headers['Host'], _ = headers['Host'].split(':', 1)

            if 'Origin' in headers:
                headers['Origin'], _ = headers['Origin'].split(':', 1)

            return headers

        self.client.ws_set_options(path=self._get_path(), headers=fix_websocket_headers)
