from setuptools import setup, find_packages

VERSION = '0.0.1'
DESCRIPTION = 'XSense Python Module'
LONG_DESCRIPTION = 'Python module to interact with XSense Home Security'


setup(
    name="xsense",
    version=VERSION,
    author="Theo Snelleman",
    author_email="<theo@snelleman.net>",
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
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
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Education",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
    ]
)