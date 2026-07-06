########################
XSense app communication
########################

The XSense Home Security is using AWS to host the API-server and uses several AWS function for authentiation.

**************
Authentication
**************

The authentication is based on AWS Cognito and uses the User pool authentication flow and
Secure Remote Password (SRP) protocol.(user_srp_auth).

This authentication works in 2 steps and are sent to https://cognito-idp.us-east-1.amazonaws.com.
For the authentication, som information about the Cognito Client ID and userpool are needed.
See below how to retrieve those via the normal API.

AWS Cognito with SRP involves a two-step process where the client application sends the username to AWS Cognito,
which responds with a salt and verifier. The client then uses this information, along with the user's password,
to compute a shared secret that is used for authentication. The server will respond with an access_token,
an id_token and a refresh_token.

**********
XSense API
**********

Structure
=========
The normal API is based on HTTPS and is using the endpoint https://api.x-sense-iot.com/app. Requests are sent
using POST and have a body with at least the following parameters::

    {
        "mac": <ID>,
        "clientType": "<clientType>"
        "appVersion": "<version>"
        "bizCode": "<code>"
        "appCode": "<appCode>"
        ...
    }

The MAC is set to 'abcdefg' for some requests, contains a hash of the parameters sent in the request as integrity check.
See below

Clienttype: 1 for IOS, 2 for Android.

App-version currently is "v1.36.0_20260130".

AppCode looks like an encoded version of the App-version and is currently 1360 (v **1** . **36** . **0** _20260130)

The bizCode specifies which command is requested.


Some requests can be unauthenticated, other must be authenticated. Authention can be added with the following header::

    'Authorization: <access_token>'


MAC-hash
--------
All requests must include a MAC-hash. This is a md5-hash calculated over the values of all custom fields included in the
request combined with the secret key. Container values are serialized in the compact JSON form used by the Android app.

Commands
========
The following requests have been identified:

+------------+---------------------------+-----------------+
| code       | description               | notes           |
+============+===========================+=================+
| 101001     | Current client id+pool    | unauthenticated |
+------------+---------------------------+-----------------+
| 102002     | Push registration request | FCM token       |
+------------+---------------------------+-----------------+
| 101003     | obtain outh               |                 |
+------------+---------------------------+-----------------+
| 101008     | All countries + regions   | Unauthenticated |
+------------+---------------------------+-----------------+
| 102007     | Query houses              |                 |
+------------+---------------------------+-----------------+
| 102008     | Query rooms               |                 |
+------------+---------------------------+-----------------+
| 104001     | Query daily history       |                 |
+------------+---------------------------+-----------------+
| 104006     | Query monthly history     |                 |
+------------+---------------------------+-----------------+
| 104007     | Query station history     | station/device  |
+------------+---------------------------+-----------------+
| 104008     | Query station month       | station/device  |
+------------+---------------------------+-----------------+
| 104009     | Query device CO history   | device          |
+------------+---------------------------+-----------------+
| 104010     | Query device CO details   | device          |
+------------+---------------------------+-----------------+
| 104014     | Query station CO history  | station         |
+------------+---------------------------+-----------------+
| 104015     | Query station CO details  | station         |
+------------+---------------------------+-----------------+
| 104020     | Query STH chart history   | temp/humidity   |
+------------+---------------------------+-----------------+
| 107002     | Get profile info          |                 |
+------------+---------------------------+-----------------+
| 120001     | Exception log             |                 |
+------------+---------------------------+-----------------+
| 505001     | Query dispatch history    | security        |
+------------+---------------------------+-----------------+


101001: Current Client ID
-------------------------
Call is needed to retrieve information about the AWS Cognito App, needed to login. Android an IOS have a separate App.

101002: Push registration request
---------------------------------
Call to register device id for push-notifications using FCM.

Params:
 :userName: email
 :pushToken: string
 :sandbox: 0

Response:
 :snsArn: string (unknown)

101003: obtain "outh", keys for MQTT
------------------------------------
Internally described as "outh", retrieve keys that are needed to make a connection to MQTT over websockets.

Params:
 :userName: email

Response:
 :accessKeyId: string
 :expiration: Datetime
 :secretAccessKey: string
 :sessionToken: string

101008: All countries + regions
-------------------------------
Call is used for displaying all regions in the registration-page. Not sure if this is needed in other places.


102007: Query houses
--------------------
Params:
 :utctimestamp: int / 0

Response:
 :createTime: Datetime
 :houseId: string
 :houseName: string
 :houseOrigin: int
 :houseRegion: string
 :loraBand: string
 :mqttRegion: string
 :mqttServer: string

102008: Query rooms
--------------------
Params:
 :utctimestamp: int / 0
 :houseId: string

104001: Query daily history
---------------------------
Params:
 :houseId: string
 :dayTime: string (yyyyMMdd)
 :timeZone: string
 :nextToken: string (optional)

Response:
 :alarms: list
 :nextToken: string

104006: Query monthly history
-----------------------------
Params:
 :houseId: string
 :hisMonth: string (yyyyMM)
 :timeZone: string

Response:
 :history counts: list

104007: Query station history
-----------------------------
Params:
 :houseId: string
 :stationId: string
 :deviceId: string (optional)
 :dayTime: string (yyyyMMdd)
 :timeZone: string
 :nextToken: string (optional)

Response:
 :alarms: list
 :nextToken: string

104008: Query station monthly history
-------------------------------------
Params:
 :houseId: string
 :stationId: string
 :deviceId: string
 :hisMonth: string (yyyyMM)
 :timeZone: string

Response:
 :history counts: list

104009 / 104014: Query CO PPM history list
------------------------------------------
104009 is used when querying a specific device. 104014 is used when querying a station.

Params:
 :stationId: string
 :deviceId: string (104009 only)
 :timeZone: string

Response:
 :CO PPM history days: list

104010 / 104015: Query CO PPM history details
---------------------------------------------
104010 is used when querying a specific device. 104015 is used when querying a station.

Params:
 :houseId: string
 :stationId: string
 :deviceId: string (104010 only)
 :dayTime: string (yyyyMMdd)
 :timeZone: string

Response:
 :CO PPM readings: list

104020: Query temperature/humidity chart history
------------------------------------------------
Params:
 :houseId: string
 :stationId: string
 :lastTime: string
 :nextToken: string (optional)

Response:
 :dataList: list
 :lastTime: string
 :nextToken: string


107002: Get profile info
------------------------
Get information about your user-profile.

Params:
 none

Response:
 :googleHide: boolean
 :nickName: string
 :userId: uuid
 :userName: email

120001: Exception log
---------------------
Looks like an API to log client errors

505001: Query security dispatch history
---------------------------------------
Params:
 :serverId: string
 :nextToken: string (optional)

Response:
 :dispatch history: list
 :nextToken: string

506001: query trial state
-------------------------
Doesn't seem to be used anymore, returns -1


