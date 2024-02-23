import base64
import sys
from unittest.mock import MagicMock, patch

import pytest

from xsense import xsense as xsense_mod


@pytest.fixture
def requests():
    """Mock fixture for requests."""""
    mock = MagicMock()
    mock.post.return_value = mock
    mock.get.return_value = mock

    with patch.object(xsense_mod, 'requests', mock):
        yield mock


@pytest.fixture
def boto3():
    """Mock fixture for boto3."""
    mock = MagicMock()
    mock.Session.return_value = mock
    mock.client.return_value = mock
    mock.initiate_auth.return_value = mock

    with patch.object(xsense_mod, 'boto3', mock):
        yield mock


@pytest.fixture
def pycognito():
    """Mock fixture for pycognito."""
    mock = MagicMock()
    mock.client.return_value = mock

    with patch.object(xsense_mod, 'AWSSRP', mock):
        yield mock



def test_sync_xsense(requests, boto3, pycognito):
    """Test sychronous xsense."""

    requests.json.return_value = {
        'reCode': 200,
        'reData': {
            'clientId': 'rip dearbytes',
            'clientSecret': base64.b64encode(b'1234waarblijftmijnvrijdagbier'),
            'cgtRegion': 'den haag ofzo weet ik veel',
            'userPoolId': 'pool is closed',
        }
    }
    xsense = xsense_mod.XSense()
    xsense.init()
    assert requests.post.called


    boto3.initiate_auth.return_value = {
        'ChallengeParameters': {
            'USERNAME': 'theo de snelste man die alles kan (behalve unit tests schrijven helaas)',
        }
    }
    requests.json.return_value = {
        'reCode': 200,
        'reData': {
            'accessKeyId': 'wanneer kom je weer bij fox werken?',
            'secretAccessKey': 'ome gertjan mist je ook',
            'sessionToken': 'theo ik verwacht hier een biertje voor',
            'expiration': 'groetjes, je favoriete ex-collega'
        }
    }
    xsense.login('username', 'password')
    assert requests.post.called

    requests.json.side_effect = [
        {
            'reCode': 200,
            'reData': [
                {
                    'houseId': '1337',
                    'houseName': 'theos fantastische cyber kelder',
                    'houseRegion': 'de kelder',
                    'mqttRegion': 'cyberspace',
                    'mqttServer': 'regenboog.kelder.io',
                }
            ]
        }, {
            'reCode': 200,
            'reData': {
                'rooms': [],
                'roomSort': 'ASC'
            }
        }, {
            'reCode': 200,
            'reData': {
                'stations': [],
                'stationSort': 'ASC'
            }
        }
    ]
    xsense.load_all()
