from setuptools import setup, find_packages

VERSION = '0.0.5'
DESCRIPTION = 'XSense Python Module'

with open('README.rst', 'r') as fd:
    LONG_DESCRIPTION = fd.read()

setup(
    name='python-xsense',
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    url='https://github.com/theosnel/python-xsense',
    license='MIT',
    author='Theo Snelleman',
    author_email='<python@theo.snelleman.net>',
    packages=find_packages(),
    install_requires=[
        'requests',
        'boto3',
        'botocore',
        'pycognito'
    ],
    extras_require={'async': ['aiohttp']},

    keywords=['python', 'xsense'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Education',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ]
)