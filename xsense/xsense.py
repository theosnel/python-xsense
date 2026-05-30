from datetime import datetime
from typing import Dict, List, Optional, Union

import requests

from xsense.aws_signer import AWSSigner
from xsense.base import XSenseBase
from xsense.entity import Entity
from xsense.entity_map import entities
from xsense.exceptions import APIFailure, SessionExpired, NotFoundError, XSenseError
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

    def get_house(self, house: House, page: str):
        if self._aws_token_expiring():
            self.load_aws()

        url, headers = self._house_request(house, page)
        res = requests.get(url, headers=headers)
        self._lastres = res
        return res.json()

    def get_thing(self, station: Station, page: str):
        if self._aws_token_expiring():
            self.load_aws()

        url, headers = self._thing_request(station, page)
        res = requests.get(url, headers=headers)
        self._lastres = res
        return res.json()

    def do_thing(self, station: Station, page: str, data: Dict):
        if self._aws_token_expiring():
            self.load_aws()

        url, headers = self._thing_request(station, page, data)
        res = requests.post(url, headers=headers, json=data)
        self._lastres = res
        return res.json()

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
        if self.signer:
            self.signer.update(self.aws_access_key, self.aws_secret_access_key, self.aws_session_token)
        else:
            self.signer = AWSSigner(self.aws_access_key, self.aws_secret_access_key, self.aws_session_token)

    def load_all(self):
        result = {}
        for i in self.get_houses():
            h = House(
                self.signer,
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

    def get_house_state(self, house: House):
        for page in ('mainpage', '2nd_mainpage'):
            res = self.get_house(house, page)

            if self._lastres.status_code == 404:
                continue

            if 'reported' in res.get('state', {}):
                self._parse_get_house_state(house, res['state']['reported'])
            # else:
            #     raise APIFailure(f'Unable to retrieve station data: {self._lastres.status_code}/{self._lastres.text}')

    def get_alarm_state(self, station: Station):
        res = self.get_thing(station, '2nd_safemode')

        if self._lastres.status_code == 404:
            return

        if 'reported' in res.get('state', {}):
            station.set_alarm_data(res['state']['reported'])

    def get_station_state(self, station: Station):
        res = None
        if station.type not in ('SBS50', 'SC07-WX', 'XC04-WX'):
            res = self.get_thing(station, f'info_{station.sn}')

        if res is None or self._lastres.status_code == 404:
            res = self.get_thing(station, f'2nd_info_{station.sn}')

        if self._lastres.status_code == 404:
            return

        if 'reported' in res.get('state', {}):
            station.set_data(res['state']['reported'])
        else:
            raise APIFailure(f'Unable to retrieve station data: {self._lastres.status_code}/{self._lastres.text}')

    def get_state(self, station: Station):
        if not station.devices:
            return

        res = None
        if station.type not in ('SBS10',):
            res = self.get_thing(station, '2nd_mainpage')

        if res is None or self._lastres.status_code == 404:
            res = self.get_thing(station, f'mainpage')

        if 'reported' in res.get('state', {}):
            self.parse_get_state(station, res['state']['reported'])
        else:
            raise APIFailure(f'Unable to retrieve station data: {self._lastres.status_code}/{self._lastres.text}')

    def set_state(self, entity: Entity, shadow: str, topic: str, definition: Dict):
        station, data = self.build_desired_state(entity, shadow, definition)

        return self.do_thing(station, topic, data)

    def set_device_config(self, entity: Entity, **values):
        shadow = "infoBase" if isinstance(entity, Station) else "infoDev"
        station, data = self.build_config_state(entity, shadow, values)
        return self.do_thing(station, f'2nd_cfg_{entity.sn}', data)

    def set_alarm_volume(self, entity: Entity, volume: int, alarm_tone: Optional[str]=None, mute: Optional[str]=None):
        self._validate_volume(volume)
        values = {
            "alarmVol": str(volume),
        }
        if alarm_tone is not None:
            values["alarmTone"] = alarm_tone
        if mute is not None:
            values["mute"] = mute

        shadow = "infoBase" if isinstance(entity, Station) else "infoDev"
        station, data = self.build_config_state(entity, shadow, values)
        return self.do_thing(station, f'2nd_cfg_{entity.sn}', data)

    def set_voice_volume(self, station: Station, volume: int):
        self._validate_volume(volume)
        station, data = self.build_config_state(station, "infoBase", {"voiceVol": str(volume)})
        return self.do_thing(station, f'2nd_cfg_{station.sn}', data)

    def set_station_mode(self, station: Station, safe_mode: str, force_arm: Optional[str]=None):
        values = {
            "userParam": "source=1",
            "source": "1",
            "safeMode": safe_mode,
        }
        if force_arm is not None:
            values["forceArm"] = force_arm

        station, data = self.build_command_state(
            station,
            "appMode",
            values,
            include_device=False,
            include_time=False
        )
        return self.do_thing(station, "2nd_appmode", data)

    def trigger_sos(self, station: Station, sos_type: str='1'):
        station, data = self.build_command_state(
            station,
            "sosDown",
            {
                "userParam": "source=1",
                "sosType": sos_type,
            },
            include_device=False
        )
        return self.do_thing(station, "2nd_sosdown", data)

    def cancel_sos(self, station: Station):
        station, data = self.build_command_state(
            station,
            "sosDown",
            {"sosStatus": "0"},
            include_device=False
        )
        return self.do_thing(station, "sosdown", data)

    def cancel_alarm(self, station: Station):
        station, data = self.build_command_state(
            station,
            "alarmCancel",
            {"cancelTime": self._utc_timestamp()},
            include_device=False,
            include_time=False
        )
        return self.do_thing(station, "alarmcancel", data)

    def set_fire_drill(
            self,
            entity: Entity,
            drill: Union[bool, str]=True,
            drill_time: Optional[str]=None,
            alarm_type: Optional[str]=None,
            alarm_vol: Optional[str]=None,
            alarm_tone: Optional[str]=None,
            location: Optional[str]=None,
            stop_reason: Optional[str]=None
    ):
        values = {"drill": self._bool_value(drill)}
        optional = {
            "drillTime": drill_time,
            "alarmType": alarm_type,
            "alarmVol": alarm_vol,
            "alarmTone": alarm_tone,
            "location": location,
            "stopReason": stop_reason,
        }
        values.update({k: v for k, v in optional.items() if v is not None})
        if not isinstance(entity, Station):
            values["deviceType"] = entity.type

        station, data = self.build_command_state(
            entity,
            "appFireDrill",
            values,
            include_device=not isinstance(entity, Station)
        )
        return self.do_thing(station, "2nd_firedrill", data)

    def set_sos_sound(self, station: Station, sos_sound: str):
        station, data = self.build_command_state(
            station,
            "sosParam",
            {
                "userParam": "source=1",
                "sosSound": sos_sound,
            },
            include_device=False
        )
        return self.do_thing(station, "2nd_sosparam", data)

    def activate_device(self, entity: Entity):
        station, data = self.build_command_state(
            entity,
            "app2ndActivate",
            {"activate": "1"},
            include_device=True
        )
        return self.do_thing(station, "2nd_appactivate", data)

    def set_install_guide_test(
            self,
            entity: Entity,
            active: Union[bool, str]=True,
            dev_type: Optional[str]=None,
            test_time: str='180',
            detc_sens: Optional[str]=None
    ):
        values = {
            "devType": dev_type or entity.type,
            "test": self._bool_value(active),
            "testTime": test_time,
        }
        if detc_sens is not None:
            values["detcSens"] = detc_sens

        station, data = self.build_command_state(entity, "appInstallGuide", values, include_device=True)
        return self.do_thing(station, "2nd_appinstallguide", data)

    def signal_test(
            self,
            entity: Entity,
            dev_type: Optional[str]=None,
            test: Union[bool, str]=True,
            test_time: str='5'
    ):
        station, data = self.build_command_state(
            entity,
            "signalTest",
            {
                "devType": dev_type or entity.type,
                "test": self._bool_value(test),
                "testTime": test_time,
            },
            include_device=True
        )
        return self.do_thing(station, f'2nd_signaltest_{entity.sn}', data)

    def set_motion_test(self, entity: Entity, active: Union[bool, str]=True, dev_type: str='SMS01'):
        station, data = self.build_command_state(
            entity,
            "testIR",
            {
                "devType": dev_type,
                "testIR": self._bool_value(active),
            },
            include_device=True,
            include_time=False,
            include_user=False
        )
        return self.do_thing(station, "testir", data)

    def set_light_power(self, entity: Entity, on: Union[bool, str]):
        station, data = self.build_command_state(
            entity,
            "lampPower",
            {
                "userParam": "source=1",
                "isOn": self._bool_value(on),
                "dev": entity.sn,
            },
            include_device=False
        )
        return self.do_thing(station, "2nd_lamppower", data)

    def set_light_group_power(
            self,
            station: Station,
            group_id: str,
            device_sns: List[str],
            on: Union[bool, str],
            timeout: str='180'
    ):
        station, data = self.build_command_state(
            station,
            "groupLampPower",
            {
                "userParam": "source=1",
                "timeOut": timeout,
                "groupId": group_id,
                "devs": device_sns,
                "isOn": self._bool_value(on),
            },
            include_device=False
        )
        return self.do_thing(station, "2nd_grouppower", data)

    def mute_water(
            self,
            entity: Entity,
            set_type: str='0',
            silence_time: str='',
            trigger_source: Optional[str]=None
    ):
        values = {
            "setType": set_type,
            "silenceTime": silence_time,
        }
        if trigger_source is not None:
            values["triggerSource"] = trigger_source

        station, data = self.build_command_state(
            entity,
            "appWater",
            values,
            include_device=True
        )
        return self.do_thing(station, "2nd_appwater", data)

    def mute_temperature_humidity(self, entity: Entity, mute_type: str='1', sensor_type: Optional[str]=None):
        station, data = self.build_command_state(
            entity,
            "extendMute",
            {
                "muteType": mute_type,
                "type": sensor_type or entity.type,
            },
            include_device=True
        )
        return self.do_thing(station, "2nd_appmute", data)

    def mute_driveway(self, entity: Entity, mute: Union[bool, str]=True, topic: str='2nd_driveway'):
        station, data = self.build_command_state(
            entity,
            "appDriveway",
            {"mute": self._bool_value(mute)},
            include_device=True
        )
        return self.do_thing(station, topic, data)

    def action(self, entity: Entity, action: str):
        entity_def = entities.get(entity.type)
        if not entity_def:
            raise XSenseError(f'Entity type {entity.type} is unkown, action {action} not possible')

        action_def = next((a for a in entity_def.get('actions', []) if a.get('action') == action), None)
        if not action_def:
            raise XSenseError(f'Action {action} is not supported for entity type {entity.type}')

        topic = action_def.get('topic')
        if callable(topic):
            topic = topic(entity)
        return self.set_state(entity, action_def['shadow'], topic, action_def)
