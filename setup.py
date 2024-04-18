from setuptools import setup, find_packages

VERSION = '0.0.1'
DESCRIPTION = 'XSense Python Module'

with open('README.md', 'r') as fd:
    LONG_DESCRIPTION = fd.read()

setup(
    name='pyhton-xsense',
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
    extras_require={
        'test': [
            'pytest',
            'pytest-cov',
            'pytest-asyncio',
        ]
    },
    keywords=['python', 'xsense'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Education',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ]
)