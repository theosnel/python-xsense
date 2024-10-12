from enum import Enum
from typing import Callable, Dict


class EntityType(Enum):
    ALARM = 'alarm'
    BASE = "base"
    CO = "co"
    COMBI = 'combi'
    MAILBOX = 'mailbox'
    SMOKE = "smoke"
    TEMPERATURE = "temperature"
    WATER = "water"


def MuteAction(shadow: str = 'appMute', topic: str|None|Callable = '2nd_appmute', extra: Dict|None=None):
    data = {
        'action': 'mute',
        'topic': topic,
        'shadow': shadow,
    }
    if extra:
        data['extra'] = extra

    return data


def TestAction(shadow='appSelfTest'):
    return {
        'action': 'test',
        'topic': lambda x: f'2nd_selftest_{x.sn}',
        'shadow': shadow
    }


def FireDrillAction():
    return {
        'action': 'firedrill',
        'topic': '2nd_firedrill',
        'shadow': 'appFireDrill'
    }


def SATestAction(shadow = 'appSelfTest'):
    """Standalone device test."""
    return {
        'action': 'test',
        'topic': lambda x: f'appselftest_{x.sn}',
        'shadow': shadow
    }


entities = {
    'SAL51': {}, # listener
    'SAL100': {}, # listener
    'SBS10': {
        'type': EntityType.BASE,
    },
    'SBS50': {
        'type': EntityType.BASE,
        'identifier': lambda entity: f'SBS50{entity.sn}',
    },
    # SSC0A - Camera
    # SSC0B
    'SC07-WX': {
        'identifier': lambda entity: f'SC07-WX-{entity.sn}',
        'type': EntityType.COMBI,
        'actions': [
            MuteAction('1')
        ]
    },
    # 'SDA51': {}, - Driveway alarm
    # 'SES01': {}, - Door sensor
    # 'SKF01': {}, - Remote Control
    # 'SKP0A': {},
    'SMA51': {
        'type': EntityType.MAILBOX,
        'actions': [
            {
                'action': 'mute',
                'topic': lambda x: '2nd_appmailmute',
                'shadow': 'appMailMute',
                'data': {'silenceTime': '', 'setType': ''}
            },
        ],
    },
    # 'SSD01': {},
    # 'SPL51': {},
    # 'SSL51': {},
    'STH51': {
        'type': EntityType.TEMPERATURE,
        'actions': [
            TestAction('thSelfTest'),
            MuteAction('1', 'extendMute')
        ],
    },
    # 'SWL51': {},
    'SWS51': {
        'type': EntityType.WATER,
        'actions': [
            TestAction('waterSelfTest'),
            MuteAction(shadow='appWater', topic='2nd_appwater', extra={'silencetime': '', 'setType': '0'})
        ],
    },
    'XC01-M': {
        # CO RF
        'type': EntityType.CO,
        'actions': [
            TestAction(shadow='appCoSelfTest'),
            MuteAction('1', '"appCoMute')
        ]
    },
    'XC04-WX': {
        'identifier': lambda entity: f'XC04-WX-{entity.sn}',
        'type': EntityType.CO,
        'actions': [
            MuteAction('1')
        ]
    },
    'XH02-M': {},
    'XP0A-MR': {
        'type': EntityType.COMBI,
        'actions': [
            TestAction(shadow='app2ndSelfTest'),
            FireDrillAction()
        ]
    },
    'XP02S-MR': {},
    'XS01-M': {
        'type': EntityType.SMOKE,
        'actions': [
            TestAction(),
            MuteAction(),
        ],
    },
    'XS01-WX': {},
    'XS03-iWX': {
        # Smoke RF
        'type': EntityType.SMOKE,
    },
    'XS03-WX': {}
}