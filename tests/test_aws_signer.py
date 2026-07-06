import datetime as real_datetime
from unittest.mock import patch

from xsense.aws_signer import AWSSigner


class FixedDateTime(real_datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 6, 24, 12, 34, 56, tzinfo=tz)


def test_sign_headers_uses_signed_shadow_headers_and_compact_body():
    signer = AWSSigner(
        "AKIDEXAMPLE",
        "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
        "session/token+value",
    )

    with patch("xsense.aws_signer.datetime.datetime", FixedDateTime):
        headers = signer.sign_headers(
            "POST",
            "https://example.iot.us-east-1.amazonaws.com/things/thing-1/shadow/name/info/update?b=2&a=1",
            "us-east-1",
            {
                "x-amz-security-token": signer.token,
                "content-type": "application/json",
            },
            '{"state":{"desired":{"alarmVol":7}}}',
        )

    assert headers == {
        "host": "example.iot.us-east-1.amazonaws.com",
        "X-Amz-Date": "20260624T123456Z",
        "Authorization": (
            "AWS4-HMAC-SHA256 "
            "Credential=AKIDEXAMPLE/20260624/us-east-1/iotdata/aws4_request, "
            "SignedHeaders=content-type;host;x-amz-date;x-amz-security-token, "
            "Signature=a8e17c2bcba483356e251a4c478a5acfa2a1fbd86c3aa3960b55e743ac2a43ed"
        ),
    }


def test_sign_headers_accepts_dict_content_for_legacy_callers():
    signer = AWSSigner(
        "AKIDEXAMPLE",
        "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
        "session/token+value",
    )

    with patch("xsense.aws_signer.datetime.datetime", FixedDateTime):
        headers = signer.sign_headers(
            "POST",
            "https://example.iot.us-east-1.amazonaws.com/things/thing-1/shadow/name/info/update",
            "us-east-1",
            {
                "x-amz-security-token": signer.token,
                "content-type": "application/json",
            },
            {"b": 2, "a": 1},
        )

    assert headers["host"] == "example.iot.us-east-1.amazonaws.com"
    assert headers["X-Amz-Date"] == "20260624T123456Z"
    assert "Credential=AKIDEXAMPLE/20260624/us-east-1/iotdata/aws4_request" in (
        headers["Authorization"]
    )
    assert "Signature=" in headers["Authorization"]


def test_presign_url_includes_session_token_and_signature():
    signer = AWSSigner(
        "AKIDEXAMPLE",
        "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
        "session/token+value",
    )

    with patch("xsense.aws_signer.datetime.datetime", FixedDateTime):
        url = signer.presign_url(
            "wss://example.iot.us-east-1.amazonaws.com/mqtt?b=2&a=1",
            "us-east-1",
        )

    assert url == (
        "wss://example.iot.us-east-1.amazonaws.com/mqtt?"
        "X-Amz-Algorithm=AWS4-HMAC-SHA256&"
        "X-Amz-Credential=AKIDEXAMPLE%2F20260624%2Fus-east-1%2Fiotdata%2Faws4_request&"
        "X-Amz-Date=20260624T123456Z&"
        "X-Amz-SignedHeaders=host&"
        "X-Amz-Security-Token=session/token%2Bvalue&"
        "X-Amz-Signature=9971f6edd37544de95ff3aa24c852b703ee22714f38a654f88fd516eab053037"
    )
