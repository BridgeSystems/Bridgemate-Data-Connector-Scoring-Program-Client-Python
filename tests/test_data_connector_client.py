"""Unit tests for DataConnectorClient against a scripted transport; a one-for-one port of
the PHP/Java DataConnectorClientTest.
"""

import json
from pathlib import Path

import pytest

from bridgemate_dataconnector import DataConnectorClient, TransportException
from bridgemate_dataconnector.dto import (
    DataConnectorResponseData,
    ErrorType,
    ResultDTO,
    ScoringProgramDataConnectorCommands,
)
from .fake_transport import FakeTransport

GUID = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def transport():
    return FakeTransport()


@pytest.fixture
def client(transport):
    return DataConnectorClient("CLUB001", "LICENCE-KEY-123", "http://localhost:5079", transport)


def ok_response_json(command: ScoringProgramDataConnectorCommands) -> str:
    return json.dumps(
        {
            "RequestCommand": int(command),
            "DataType": int(DataConnectorResponseData.OK),
            "LastQueueItemId": 0,
            "ErrorType": int(ErrorType.None_),
            "SessionGuid": GUID,
            "SerializedData": json.dumps("OK"),
        }
    )


def test_connect_pings_the_base_address(client, transport):
    transport.responses.append("Bridgemate dataconnector service version 1.2.3")
    response = client.connect()
    assert response.data_type == DataConnectorResponseData.OK
    assert transport.calls[0] == ("http://localhost:5079/", None)


def test_connect_failure_returns_no_connection(client, transport):
    transport.responses.append(TransportException("refused"))
    response = client.connect()
    assert response.data_type == DataConnectorResponseData.Error
    assert response.error_type == ErrorType.NoConnection


def test_send_results_builds_the_envelope_and_filters_by_session(client, transport):
    transport.responses.append(ok_response_json(ScoringProgramDataConnectorCommands.PutResults))

    mine = ResultDTO()
    mine.session_guid = GUID
    mine.section_letters = "A"
    other = ResultDTO()
    other.session_guid = "F" * 32

    response = client.send_results(GUID, [mine, other])
    assert response.data_type == DataConnectorResponseData.OK

    url, body = transport.calls[0]
    assert url == "http://localhost:5079/dc-scoringprogram"
    envelope = json.loads(body)
    assert envelope["Command"] == int(ScoringProgramDataConnectorCommands.PutResults)
    assert envelope["ClubId"] == "CLUB001"
    assert envelope["LicenceKey"] == "LICENCE-KEY-123"
    assert envelope["SessionGuid"] == GUID
    payload = json.loads(envelope["SerializedData"])
    assert len(payload) == 1
    assert payload[0]["SectionLetters"] == "A"


def test_poll_for_results_uses_fixture_response_and_caches_last_queue_item_id(client, transport):
    fixture = (FIXTURES / "responses" / "PollQueueForNewResults.json").read_text(encoding="utf-8")
    transport.responses.append(fixture)

    results = client.poll_for_results(GUID)
    assert len(results) == 2
    assert all(isinstance(result, ResultDTO) for result in results)
    assert client.get_last_queue_item_id(DataConnectorResponseData.Results) == 42

    envelope = json.loads(transport.calls[0][1])
    assert envelope["Command"] == int(ScoringProgramDataConnectorCommands.PollQueueForNewResults)
    assert envelope["SerializedData"] == ""


def test_accept_queue_data_sends_the_cached_id(client, transport):
    transport.responses.append(
        (FIXTURES / "responses" / "PollQueueForNewResults.json").read_text(encoding="utf-8")
    )
    transport.responses.append(ok_response_json(ScoringProgramDataConnectorCommands.AcceptResultQueueItems))

    client.poll_for_results(GUID)
    response = client.accept_queue_data(GUID, DataConnectorResponseData.Results)
    assert response.data_type == DataConnectorResponseData.OK

    envelope = json.loads(transport.calls[1][1])
    assert envelope["Command"] == int(ScoringProgramDataConnectorCommands.AcceptResultQueueItems)
    assert envelope["SerializedData"] == "42"


def test_accept_queue_data_rejects_invalid_data_type(client, transport):
    response = client.accept_queue_data(GUID, DataConnectorResponseData.EventInfo)
    assert response.error_type == ErrorType.Validation
    assert transport.calls == []


def test_transport_failures_are_retried_five_times_then_reported_as_no_connection(client, transport):
    for _ in range(5):
        transport.responses.append(TransportException("refused"))
    response = client.send_results(GUID, [])
    assert response.error_type == ErrorType.NoConnection
    assert len(transport.calls) == 5


def test_poll_returns_empty_list_on_error_response(client, transport):
    transport.responses.append((FIXTURES / "responses" / "Error.json").read_text(encoding="utf-8"))
    assert client.poll_for_results(GUID) == []


def test_invalid_base_address_is_rejected():
    with pytest.raises(ValueError):
        DataConnectorClient("c", "l", "ftp://example.com")
