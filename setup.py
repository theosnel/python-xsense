from setuptools import setup, find_packages

VERSION = '0.1.0'
DESCRIPTION = 'Async X-Sense cloud, MQTT, and camera client'

with open('README.rst', 'r') as fd:
    LONG_DESCRIPTION = fd.read()

setup(
    name='python-xsense',
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/x-rst',
    url='https://github.com/theosnel/python-xsense',
    project_urls={
        'Source': 'https://github.com/theosnel/python-xsense',
        'Pull requests': 'https://github.com/theosnel/python-xsense/pulls',
    },
    license='MIT',
    author='Theo Snelleman',
    author_email='python@theo.snelleman.net',
    packages=find_packages(),
    python_requires='>=3.10',
    install_requires=[
        'boto3',
        'botocore',
        'pycognito',
        'aiohttp',
        'paho-mqtt>=2.1.0,<3',
    ],
    extras_require={
        'test': ['pytest'],
        'dev': ['build', 'pip-audit', 'pytest', 'twine'],
    },

    keywords=['python', 'xsense'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
        'Operating System :: OS Independent',
    ]
)
