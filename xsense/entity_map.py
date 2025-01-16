from enum import Enum
from typing import Callable, Dict


class EntityType(Enum):
    ALARM = 'alarm'
    BASE = "base"
    CO = "co"
    COMBI = 'combi'
    DOOR = 'door'
    HEAT = 'heath'
    KEYPAD = 'keypad'
    MAILBOX = 'mailbox'
    MOTION = 'motion'
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
    'SC06-WX': {
        'identifier': lambda entity: f'SC06-WX-{entity.sn}',
        'type': EntityType.COMBI,
        'actions': [
            TestAction(),
        ],
    },
    'SC07-WX': {
        'identifier': lambda entity: f'SC07-WX-{entity.sn}',
        'type': EntityType.COMBI,
        'actions': [
            MuteAction('1')
        ]
    },
    # 'SDA51': {}, - Driveway alarm
    'SDS0A': {
        'type': EntityType.DOOR,
    },
    # 'SES01': {}, - Door sensor
    # 'SKF01': {}, - Remote Control
    'SKP0A': {
        'type': EntityType.KEYPAD,
    },
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
    'SMS0A': {
        'type': EntityType.MOTION,
    },
    # 'SSD01': {},
    # 'SPL51': {},
    # 'SSL51': {},
    'STH0A': {
        'type': EntityType.TEMPERATURE,
        'actions': [
            TestAction('thSelfTest'),
            MuteAction('1', 'extendMute')
        ],
    },
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
    'XC0C-iR': {
        'type': EntityType.CO,
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
    'XH02-M': {
        'type': EntityType.HEAT,
        'actions': [
        ]
    },
    'XP0A-MR': {
        'type': EntityType.COMBI,
        'actions': [
            TestAction(shadow='app2ndSelfTest'),
            FireDrillAction()
        ]
    },
    'XP02S-MR': {
        'type': EntityType.SMOKE,
        'actions': [
            TestAction(shadow='app2ndSelfTest'),
        ]
    },
    'XS01-M': {
        'type': EntityType.SMOKE,
        'actions': [
            TestAction(),
            MuteAction(),
        ],
    },
    'XS01-WX': {
        'type': EntityType.SMOKE,
        'actions': [
            TestAction(),
        ],
    },
    'XS03-iWX': {
        # Smoke RF
        'type': EntityType.SMOKE,
    },
    'XS03-WX': {}
}