"""Unit tests for DataConnectorClient against a scripted transport; a one-for-one port of
the PHP/Java DataConnectorClientTest.
"""

import json
import os
import sys
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


def test_published_port_without_process_id_is_trusted():
    def not_expected(process_id):
        raise AssertionError("Not expected to be asked.")

    assert DataConnectorClient._published_port(5080, None, not_expected) == 5080


def test_published_port_of_a_running_data_connector_is_used():
    asked = []

    def is_running(process_id):
        asked.append(process_id)
        return True

    assert DataConnectorClient._published_port(5080, 1000, is_running) == 5080
    assert asked == [1000]


def test_published_port_of_a_data_connector_that_no_longer_runs_is_ignored():
    assert DataConnectorClient._published_port(5080, 1000, lambda process_id: False) is None


def test_invalid_published_port_is_ignored():
    assert DataConnectorClient._published_port(0, None, lambda process_id: True) is None


@pytest.mark.skipif(sys.platform != "win32", reason="Process inspection is Windows only.")
def test_process_inspection_tells_the_data_connector_from_other_and_absent_processes():
    # The test runner is a running process, but not the Data Connector.
    assert DataConnectorClient._is_data_connector_running(os.getpid()) is False
    # A process id that is not in use (process ids are multiples of 4 on Windows).
    assert DataConnectorClient._is_data_connector_running(0x7FFFFFFC) is False


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
