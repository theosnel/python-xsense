import asyncio
import base64
import json
import time
from types import SimpleNamespace

from xsense.webrtc_signal import (
    SIGNAL_MODE,
    SIGNAL_VIEWER_TYPE,
    XSenseWebRTCTicket,
    XSenseWebRTCSignalSession,
    make_ice_candidate_payload,
    make_sdp_offer_payload,
    parse_signal_message,
)


def _decode_payload(envelope: dict):
    return json.loads(base64.b64decode(envelope["messagePayload"]).decode())


def _ticket(**overrides):
    data = {
        "signalServer": "https://signal.example/ws",
        "groupId": "group-id",
        "role": "viewer",
        "id": "client-id",
        "traceId": "trace-id",
        "sign": "signed-value",
        "time": "1710000000000",
        "expirationTime": str(int(time.time() * 1000) + 60_000),
        "signalPingInterval": "30",
        "appStopLiveTimeout": "45",
        "signalServerIpAddress": "203.0.113.10",
        "iceServer": [{"urls": ["stun:example"]}],
    }
    data.update(overrides)
    return XSenseWebRTCTicket.from_api("CAM123", data)


def test_webrtc_ticket_parses_api_data_and_builds_signal_url():
    ticket = _ticket()

    assert ticket.serial_number == "CAM123"
    assert ticket.signal_server == "https://signal.example/ws"
    assert ticket.group_id == "group-id"
    assert ticket.role == "viewer"
    assert ticket.client_id == "client-id"
    assert ticket.trace_id == "trace-id"
    assert ticket.sign == "signed-value"
    assert ticket.time == 1710000000000
    assert ticket.signal_ping_interval == 30
    assert ticket.app_stop_live_timeout == 45
    assert ticket.ice_servers == [{"urls": ["stun:example"]}]
    assert ticket.is_valid is True
    assert ticket.signal_url() == (
        "wss://signal.example/group-id/viewer/client-id?"
        "traceId=trace-id&time=1710000000000&sign=signed-value&name=test-123"
    )


def test_webrtc_ticket_connect_options_use_signal_ip_override():
    ticket = _ticket(signalServer="wss://signal.example:443/ws")

    assert ticket.signal_connect_options() == {
        "url": (
            "wss://203.0.113.10:443/group-id/viewer/client-id?"
            "traceId=trace-id&time=1710000000000&sign=signed-value&name=test-123"
        ),
        "headers": {"Host": "signal.example:443"},
        "server_hostname": "signal.example",
    }


def test_make_sdp_offer_payload_uses_apk_envelope():
    ticket = _ticket(signalServer="wss://signal.example")
    payload = make_sdp_offer_payload(
        offer_sdp=(
            "v=0\r\n"
            "m=video 9 UDP/TLS/RTP/SAVPF 96\r\n"
            "a=mid:0\r\n"
            "a=recvonly\r\n"
            "a=candidate:1 1 udp 1 192.0.2.10 123 typ host\r\n"
        ),
        ticket=ticket,
        recipient_client_id="CAM123",
        session_id="session-id",
        resolution="1920x1080",
    )

    envelope = json.loads(payload)
    decoded = _decode_payload(envelope)

    assert envelope["messageType"] == "SDP_OFFER"
    assert envelope["mode"] == SIGNAL_MODE
    assert envelope["viewerType"] == SIGNAL_VIEWER_TYPE
    assert envelope["senderClientId"] == "client-id"
    assert envelope["recipientClientId"] == "CAM123"
    assert envelope["sessionId"] == "session-id"
    assert envelope["resolution"] == "1920x1080"
    assert decoded["type"] == "offer"
    assert "a=recvonly" in decoded["sdp"]
    assert "a=candidate:" not in decoded["sdp"]


def test_make_ice_candidate_payload_uses_apk_envelope():
    ticket = _ticket()

    payload = make_ice_candidate_payload(
        candidate="candidate:1 1 udp 1 192.0.2.10 123 typ host",
        sdp_mid="0",
        sdp_m_line_index=0,
        ticket=ticket,
        recipient_client_id="CAM123",
        session_id="session-id",
    )

    envelope = json.loads(payload)
    decoded = _decode_payload(envelope)

    assert envelope["messageType"] == "ICE_CANDIDATE"
    assert envelope["senderClientId"] == "client-id"
    assert envelope["recipientClientId"] == "CAM123"
    assert decoded == {
        "sdpMid": "0",
        "sdpMLineIndex": 0,
        "candidate": "candidate:1 1 udp 1 192.0.2.10 123 typ host",
    }


def test_parse_signal_message_decodes_answer_and_candidate_payloads():
    answer_payload = base64.b64encode(
        json.dumps({"type": "answer", "sdp": "v=0\r\n"}).encode()
    ).decode()
    event, payload = parse_signal_message(
        json.dumps(
            {
                "messageType": "SDP_ANSWER",
                "senderClientId": "CAM123",
                "recipientClientId": "client-id",
                "messagePayload": answer_payload,
            }
        )
    )

    assert event == "SDP_ANSWER"
    assert payload["messagePayload"] == answer_payload

    candidate_payload = json.dumps(
        {"candidate": "candidate:1 1 udp 1 192.0.2.10 123 typ host"}
    )
    event, payload = parse_signal_message(
        json.dumps(
            {
                "messageType": "ICE_CANDIDATE",
                "messagePayload": candidate_payload,
            }
        )
    )

    assert event == "ICE_CANDIDATE"
    assert payload == {"candidate": "candidate:1 1 udp 1 192.0.2.10 123 typ host"}


def test_parse_signal_message_decodes_encoded_peer_payload():
    peer_payload = base64.b64encode(json.dumps({"clientId": "CAM123"}).encode()).decode()

    event, payload = parse_signal_message(
        json.dumps({"messageType": "PEER_IN", "messagePayload": peer_payload})
    )

    assert event == "PEER_IN"
    assert payload == {"clientId": "CAM123"}


def test_trickled_candidate_is_queued_until_answer_is_received():
    async def run_test():
        class FakeWs:
            closed = False

            def __init__(self):
                self.messages = []

            async def send_str(self, message):
                self.messages.append(json.loads(message))

        session = XSenseWebRTCSignalSession(
            session=object(),
            ticket=_ticket(),
            offer_sdp="v=0\r\n",
            resolution="1920x1080",
            camera_online=True,
        )
        candidate = SimpleNamespace(
            candidate="candidate:1 1 udp 1 192.0.2.1 123 typ host",
            sdp_mid="0",
            sdp_m_line_index=0,
        )

        await session.add_candidate(candidate)

        assert len(session._pending_remote_candidates) == 1

        session._ws = FakeWs()
        session._offer_sent = True

        await session.add_candidate(candidate)

        assert len(session._pending_remote_candidates) == 2
        assert session._ws.messages == []

        session._answer.set_result("v=0\r\n")
        await session._flush_pending_remote_candidates()

        assert session._pending_remote_candidates == []
        assert [message["messageType"] for message in session._ws.messages] == [
            "ICE_CANDIDATE",
            "ICE_CANDIDATE",
        ]
        assert session._sent_candidate_count == 2

    asyncio.run(run_test())
