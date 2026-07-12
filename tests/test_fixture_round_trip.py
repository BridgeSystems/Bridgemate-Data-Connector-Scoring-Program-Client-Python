"""Golden fixture round-trips.

The fixtures are the exact JSON the .NET client produces. Decoding a fixture into the
generated DTOs and re-encoding it must yield a structurally identical document (including the
nested SerializedData payload); any missing, extra or mistyped property fails these tests.
The comparison is on parsed JSON because the .NET serializer escapes differently (e.g. \\u0022)
than Python.
"""

import json
from pathlib import Path

import pytest

from bridgemate_dataconnector.dto import (
    Bridgemate2SettingsDTO,
    Bridgemate3SettingsDTO,
    ContinueDTO,
    HandrecordDTO,
    InitDTO,
    ParticipationDTO,
    PlayerDataDTO,
    ResultDTO,
    ScoringGroupDTO,
    ScoringProgramRequest,
    ScoringProgramResponse,
    SectionUpdateDTO,
    TdCallDTO,
)

FIXTURES = Path(__file__).parent / "fixtures"
REQUEST_FIXTURES = sorted((FIXTURES / "requests").glob("*.json"))
RESPONSE_FIXTURES = sorted((FIXTURES / "responses").glob("*.json"))

# Maps a request fixture to the payload DTO class inside SerializedData.
# A [Cls] entry means a JSON array of that DTO; None means the payload is not a DTO
# (a bare JSON string or number, or empty).
REQUEST_PAYLOADS = {
    "Ping": None,
    "InitializeEvent": InitDTO,
    "ContinueEvent": ContinueDTO,
    "UpdateMovement": SectionUpdateDTO,
    "UpdateScoringGroups": [ScoringGroupDTO],
    "PutResults": [ResultDTO],
    "PutPlayerData": [PlayerDataDTO],
    "PutParticipations": [ParticipationDTO],
    "PutHandrecords": [HandrecordDTO],
    "PutTdCalls": [TdCallDTO],
    "PutBridgemate2Settings": [Bridgemate2SettingsDTO],
    "PutBridgemate3Settings": [Bridgemate3SettingsDTO],
}

RESPONSE_PAYLOADS = {
    "PollQueueForNewResults": [ResultDTO],
    "PollQueueForNewPlayerData": [PlayerDataDTO],
    "PollQueueForNewParticipations": [ParticipationDTO],
    "PollQueueForNewHandrecords": [HandrecordDTO],
    "PollQueueForNewTdCalls": [TdCallDTO],
}


def _normalize(envelope: dict) -> dict:
    """Replaces the SerializedData string with its parsed JSON so the comparison ignores
    serializer-specific string escaping.
    """
    envelope = dict(envelope)
    if envelope.get("SerializedData"):
        envelope["SerializedData"] = json.loads(envelope["SerializedData"])
    return envelope


def _assert_payload_round_trips(payload_type, serialized_data: str):
    payload = json.loads(serialized_data)
    if isinstance(payload_type, list):
        dto_class = payload_type[0]
        re_encoded = [dto_class.from_dict(item).to_dict() for item in payload]
    else:
        re_encoded = payload_type.from_dict(payload).to_dict()
    # Round-trip through json to turn any enum members back into plain ints.
    assert payload == json.loads(json.dumps(re_encoded))


@pytest.mark.parametrize("path", REQUEST_FIXTURES, ids=lambda p: p.stem)
def test_request_envelope_round_trips(path):
    original = json.loads(path.read_text(encoding="utf-8"))
    request = ScoringProgramRequest.from_dict(original)
    re_encoded = json.loads(json.dumps(request.to_dict()))
    assert _normalize(original) == _normalize(re_encoded)


@pytest.mark.parametrize("path", REQUEST_FIXTURES, ids=lambda p: p.stem)
def test_request_payload_round_trips(path):
    payload_type = REQUEST_PAYLOADS.get(path.stem)
    if payload_type is None:
        return  # The payload is not a DTO; the envelope test already covers it.
    envelope = json.loads(path.read_text(encoding="utf-8"))
    _assert_payload_round_trips(payload_type, envelope["SerializedData"])


@pytest.mark.parametrize("path", RESPONSE_FIXTURES, ids=lambda p: p.stem)
def test_response_envelope_round_trips(path):
    original = json.loads(path.read_text(encoding="utf-8"))
    response = ScoringProgramResponse.from_dict(original)
    re_encoded = json.loads(json.dumps(response.to_dict()))
    assert _normalize(original) == _normalize(re_encoded)


@pytest.mark.parametrize("path", RESPONSE_FIXTURES, ids=lambda p: p.stem)
def test_response_payload_round_trips(path):
    payload_type = RESPONSE_PAYLOADS.get(path.stem)
    if payload_type is None:
        return  # The payload is not a DTO; the envelope test already covers it.
    envelope = json.loads(path.read_text(encoding="utf-8"))
    _assert_payload_round_trips(payload_type, envelope["SerializedData"])
