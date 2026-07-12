"""The scoring program client. See DataConnectorClient."""

import json
import re
import time

from .dto import (
    Bridgemate2SettingsDTO,
    Bridgemate3SettingsDTO,
    ContinueDTO,
    DataConnectorResponseData,
    ErrorType,
    HandrecordDTO,
    InitDTO,
    ParticipationDTO,
    PlayerDataDTO,
    ResultDTO,
    ScoringGroupDTO,
    ScoringProgramDataConnectorCommands,
    ScoringProgramRequest,
    ScoringProgramResponse,
    SectionUpdateDTO,
    TdCallDTO,
)
from .http_transport import HttpTransport
from .transport_exception import TransportException
from .urllib_transport import UrllibTransport


def _encode(data) -> str:
    """Serializes a DTO or a list of DTOs to compact JSON, like System.Text.Json does."""
    if isinstance(data, list):
        return json.dumps([dto.to_dict() for dto in data], separators=(",", ":"))
    return json.dumps(data.to_dict(), separators=(",", ":"))


class DataConnectorClient:
    """Scoring program client for the Bridgemate Data Connector over http.

    The wire behaviour mirrors the .NET ScoringProgramDataConnectorHttpClient: a JSON serialized
    ScoringProgramRequest is POSTed to the dc-scoringprogram endpoint and answered with a JSON
    serialized ScoringProgramResponse. Since http is stateless there is no persistent connection:
    connect() is a ping and there is no disconnect.

    Methods never raise on communication problems; they return a ScoringProgramResponse with
    data_type Error (poll methods return an empty list), exactly like the .NET client.
    """

    # The default http port of the Data Connector.
    DEFAULT_PORT = 5079

    # The endpoint that handles scoring program requests.
    SCORING_PROGRAM_ENDPOINT = "dc-scoringprogram"

    # Part of the expected response body when pinging the Data Connector with a GET request.
    API_PING_RESPONSE = "Bridgemate dataconnector service version"

    def __init__(
        self,
        club_id: str,
        licence_key: str,
        base_address: str | None = None,
        transport: HttpTransport | None = None,
    ):
        """Creates the client.

        club_id: the id of the club that is using the client. Required for http communication.
        licence_key: the licence key for the club using the client. Required for http communication.
        base_address: the base address of the Data Connector host, e.g. "http://192.168.1.50:5079".
            When None the client targets the Data Connector on the local computer, discovering its
            port through the Windows registry (default 5079). On non-Windows hosts pass the address
            explicitly.
        transport: override the http implementation; used by tests and by the wire trace.
        """
        self._club_id = club_id
        self._licence_key = licence_key
        if base_address is not None:
            trimmed = base_address.rstrip("/")
            if not re.match("^https?://", trimmed, re.IGNORECASE):
                raise ValueError(f"'{base_address}' is not an absolute http or https url.")
            self._base_address = trimmed
        else:
            self._base_address = self.discover_local_base_address()
        self._transport = transport if transport is not None else UrllibTransport()
        # The id of the last downloaded queue item per data type, cached by the poll methods and
        # used by accept_queue_data. Keyed by the int value of DataConnectorResponseData.
        self._last_queue_item_ids: dict[int, int] = {}

    @property
    def base_address(self) -> str:
        """The base address in use, e.g. "http://localhost:5079"."""
        return self._base_address

    @staticmethod
    def discover_local_base_address() -> str:
        """The url of the Data Connector on the local computer.

        On Windows the Data Connector service publishes the port it listens on in the registry
        (HKEY_CURRENT_USER\\Software\\Bridge Systems BV\\BridgemateDataConnector, value HttpPort);
        when nothing is published the default port 5079 is assumed.
        """
        try:
            import winreg  # Only available on Windows; guarded by the except below.

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Bridge Systems BV\BridgemateDataConnector"
            ) as key:
                value, value_type = winreg.QueryValueEx(key, "HttpPort")
                if value_type == winreg.REG_DWORD and 0 < value <= 65535:
                    return f"http://localhost:{value}"
        except (ImportError, OSError):
            # Non-Windows host, or the key/value is absent: fall through to the default.
            pass
        return f"http://localhost:{DataConnectorClient.DEFAULT_PORT}"

    def connect(self) -> ScoringProgramResponse:
        """Checks if the Data Connector can be reached by sending a GET request to its base address."""
        try:
            body = self._transport.get(self._base_address + "/")
            success = self.API_PING_RESPONSE in body
        except TransportException as exception:
            body = str(exception)
            success = False
        response = ScoringProgramResponse()
        response.request_command = ScoringProgramDataConnectorCommands.Connect
        response.data_type = (
            DataConnectorResponseData.OK if success else DataConnectorResponseData.Error
        )
        response.error_type = ErrorType.None_ if success else ErrorType.NoConnection
        response.serialized_data = json.dumps(body)
        return response

    def ping(self) -> ScoringProgramResponse:
        """Checks that the Data Connector is responsive by sending it a piece of data that it
        must echo.
        """
        # The .NET client sends the current time in ticks; any unique string would do.
        request_ticks = str(int(time.time() * 10_000_000))
        response = self._send("", ScoringProgramDataConnectorCommands.Ping, json.dumps(request_ticks))
        if response.request_command != ScoringProgramDataConnectorCommands.Ping:
            return self._error_response(
                ScoringProgramDataConnectorCommands.Ping,
                ErrorType.Unknown,
                f"Invalid command in response to Ping: '{response.request_command.name}'",
            )
        if response.data_type != DataConnectorResponseData.OK:
            return response
        response_ticks = json.loads(response.serialized_data or "null")
        error = response_ticks != request_ticks
        result = ScoringProgramResponse()
        result.request_command = ScoringProgramDataConnectorCommands.Ping
        result.data_type = (
            DataConnectorResponseData.Error if error else DataConnectorResponseData.OK
        )
        result.error_type = ErrorType.Validation if error else ErrorType.None_
        result.serialized_data = response.serialized_data
        return result

    def initialize(self, init_dto: InitDTO) -> ScoringProgramResponse:
        """Instructs BCS to create a new event with the provided sessions, scoring groups,
        sections, tables and rounds. Player data, participations and handrecords can be included.
        """
        return self._send("", ScoringProgramDataConnectorCommands.InitializeEvent, _encode(init_dto))

    def continue_event(self, continue_dto: ContinueDTO) -> ScoringProgramResponse:
        """Instructs BCS to continue working with a previously created event."""
        return self._send("", ScoringProgramDataConnectorCommands.ContinueEvent, _encode(continue_dto))

    def update_movement(self, updated_section: SectionUpdateDTO) -> ScoringProgramResponse:
        """Updates the movement for a section, or deletes the section."""
        return self._send(
            updated_section.session_guid or "",
            ScoringProgramDataConnectorCommands.UpdateMovement,
            _encode(updated_section),
        )

    def update_scoring_groups(self, scoring_groups: list[ScoringGroupDTO]) -> ScoringProgramResponse:
        """Updates the scoring method of the scoring groups and/or rearranges the assignment of
        the sections to them. Sends one request per session, like the .NET client.
        """
        groups: dict[str, list[ScoringGroupDTO]] = {}
        for scoring_group in scoring_groups:
            groups.setdefault(scoring_group.session_guid or "", []).append(scoring_group)
        for session_guid, groups_for_session in groups.items():
            response = self._send(
                session_guid,
                ScoringProgramDataConnectorCommands.UpdateScoringGroups,
                _encode(groups_for_session),
            )
            if response.data_type != DataConnectorResponseData.OK:
                return response
        response = ScoringProgramResponse()
        response.request_command = ScoringProgramDataConnectorCommands.UpdateScoringGroups
        response.data_type = DataConnectorResponseData.OK
        response.serialized_data = json.dumps("Scoring groups updated.")
        return response

    def send_results(self, session_guid: str, results: list[ResultDTO]) -> ScoringProgramResponse:
        """Sends board results to the BCS queue. Only DTOs whose session_guid matches are sent."""
        return self._send_for_session(session_guid, ScoringProgramDataConnectorCommands.PutResults, results)

    def send_player_data(self, session_guid: str, player_data: list[PlayerDataDTO]) -> ScoringProgramResponse:
        """Sends player data to the BCS queue. Only DTOs whose session_guid matches are sent."""
        return self._send_for_session(session_guid, ScoringProgramDataConnectorCommands.PutPlayerData, player_data)

    def send_participations(self, session_guid: str, participations: list[ParticipationDTO]) -> ScoringProgramResponse:
        """Sends participations to the BCS queue. Only DTOs whose session_guid matches are sent;
        when none match a NoData error is returned without calling the Data Connector.
        """
        for_session = self._filter_by_session(session_guid, participations)
        if not for_session:
            return self._error_response(
                ScoringProgramDataConnectorCommands.PutParticipations, ErrorType.NoData, "Empty data"
            )
        return self._send(
            session_guid, ScoringProgramDataConnectorCommands.PutParticipations, _encode(for_session)
        )

    def send_handrecords(self, session_guid: str, handrecords: list[HandrecordDTO]) -> ScoringProgramResponse:
        """Sends handrecords to the BCS queue. Only DTOs whose session_guid matches are sent."""
        return self._send_for_session(session_guid, ScoringProgramDataConnectorCommands.PutHandrecords, handrecords)

    def send_td_calls(self, session_guid: str, td_calls: list[TdCallDTO]) -> ScoringProgramResponse:
        """Sends TD calls to the BCS queue. Only DTOs whose session_guid matches are sent."""
        return self._send_for_session(session_guid, ScoringProgramDataConnectorCommands.PutTdCalls, td_calls)

    def send_bridgemate2_settings(
        self, session_guid: str, settings: list[Bridgemate2SettingsDTO]
    ) -> ScoringProgramResponse:
        """Adds or updates the Bridgemate 2 settings for the given sections. One DTO per section."""
        return self._send_for_session(
            session_guid, ScoringProgramDataConnectorCommands.PutBridgemate2Settings, settings
        )

    def send_bridgemate3_settings(
        self, session_guid: str, settings: list[Bridgemate3SettingsDTO]
    ) -> ScoringProgramResponse:
        """Adds or updates the Bridgemate 3 settings for the given sections. One DTO per section."""
        return self._send_for_session(
            session_guid, ScoringProgramDataConnectorCommands.PutBridgemate3Settings, settings
        )

    def poll_for_results(self, session_guid: str, all: bool = False) -> list[ResultDTO]:
        """Polls the queue for board results.

        all: also return results that were polled before.
        """
        return self._poll(
            session_guid,
            ScoringProgramDataConnectorCommands.PollQueueForAllResults
            if all
            else ScoringProgramDataConnectorCommands.PollQueueForNewResults,
            DataConnectorResponseData.Results,
            ResultDTO,
        )

    def poll_for_player_data(self, session_guid: str, all: bool = False) -> list[PlayerDataDTO]:
        """Polls the queue for player data.

        all: also return player data that was polled before.
        """
        return self._poll(
            session_guid,
            ScoringProgramDataConnectorCommands.PollQueueForAllPlayerData
            if all
            else ScoringProgramDataConnectorCommands.PollQueueForNewPlayerData,
            DataConnectorResponseData.PlayerData,
            PlayerDataDTO,
        )

    def poll_for_participations(self, session_guid: str, all: bool = False) -> list[ParticipationDTO]:
        """Polls the queue for participations.

        all: also return participations that were polled before.
        """
        return self._poll(
            session_guid,
            ScoringProgramDataConnectorCommands.PollQueueForAllParticipations
            if all
            else ScoringProgramDataConnectorCommands.PollQueueForNewParticipations,
            DataConnectorResponseData.Participations,
            ParticipationDTO,
        )

    def poll_for_handrecords(self, session_guid: str, all: bool = False) -> list[HandrecordDTO]:
        """Polls the queue for handrecords.

        all: also return handrecords that were polled before.
        """
        return self._poll(
            session_guid,
            ScoringProgramDataConnectorCommands.PollQueueForAllHandrecords
            if all
            else ScoringProgramDataConnectorCommands.PollQueueForNewHandrecords,
            DataConnectorResponseData.Handrecords,
            HandrecordDTO,
        )

    def poll_for_td_calls(self, session_guid: str, all: bool = False) -> list[TdCallDTO]:
        """Polls the queue for TD calls.

        all: also return TD calls that were polled before.
        """
        return self._poll(
            session_guid,
            ScoringProgramDataConnectorCommands.PollQueueForAllTdCalls
            if all
            else ScoringProgramDataConnectorCommands.PollQueueForNewTdCalls,
            DataConnectorResponseData.TdCalls,
            TdCallDTO,
        )

    def accept_queue_data(
        self, session_guid: str, data_type: DataConnectorResponseData
    ) -> ScoringProgramResponse:
        """Signals to the Data Connector that queue data of the given type, up to and including
        the last polled item, does not need to be sent again.

        data_type: Results, PlayerData, Participations, Handrecords or TdCalls.
        """
        commands = {
            DataConnectorResponseData.Results: ScoringProgramDataConnectorCommands.AcceptResultQueueItems,
            DataConnectorResponseData.PlayerData: ScoringProgramDataConnectorCommands.AcceptPlayerDataQueueItems,
            DataConnectorResponseData.Participations: ScoringProgramDataConnectorCommands.AcceptParticipantQueueItems,
            DataConnectorResponseData.Handrecords: ScoringProgramDataConnectorCommands.AcceptHandrecordQueueItems,
            DataConnectorResponseData.TdCalls: ScoringProgramDataConnectorCommands.AcceptTdCallQueueItems,
        }
        command = commands.get(data_type)
        if command is None:
            return self._error_response(
                ScoringProgramDataConnectorCommands.None_,
                ErrorType.Validation,
                f"Invalid datatype '{data_type.name}'",
            )
        last_queue_item_id = self._last_queue_item_ids.get(int(data_type), 0)
        return self._send(session_guid, command, json.dumps(last_queue_item_id))

    def get_last_queue_item_id(self, data_type: DataConnectorResponseData) -> int:
        """The id of the last queue item downloaded for the given data type, as cached by the
        poll methods. Zero when nothing has been polled yet.
        """
        return self._last_queue_item_ids.get(int(data_type), 0)

    def send_request(self, request: ScoringProgramRequest) -> ScoringProgramResponse:
        """Sends a raw request. The club id and licence key are set on the request by this method.

        All higher level methods funnel through here; use it directly for commands this client
        does not wrap yet. A breakpoint on this method shows every envelope that goes over
        the wire.
        """
        request.club_id = self._club_id
        request.licence_key = self._licence_key
        body = json.dumps(request.to_dict(), separators=(",", ":"))
        url = f"{self._base_address}/{self.SCORING_PROGRAM_ENDPOINT}"

        last_error_message = "No connection"
        for attempt in range(5):
            try:
                response_body = self._transport.post(url, body)
                decoded = json.loads(response_body)
                if not isinstance(decoded, dict):
                    return self._error_response(
                        request.command, ErrorType.EmptyResponse, "Empty response"
                    )
                return ScoringProgramResponse.from_dict(decoded)
            except (TransportException, json.JSONDecodeError) as exception:
                last_error_message = str(exception)
                # The .NET client backs off 200/400/600/800 ms between its five attempts.
                if attempt < 4:
                    time.sleep((200 + attempt * 200) / 1000)
        return self._error_response(request.command, ErrorType.NoConnection, last_error_message)

    def _send(
        self,
        session_guid: str,
        command: ScoringProgramDataConnectorCommands,
        serialized_data: str,
    ) -> ScoringProgramResponse:
        request = ScoringProgramRequest()
        request.command = command
        request.session_guid = session_guid
        request.serialized_data = serialized_data
        return self.send_request(request)

    def _send_for_session(
        self,
        session_guid: str,
        command: ScoringProgramDataConnectorCommands,
        dtos: list,
    ) -> ScoringProgramResponse:
        return self._send(session_guid, command, _encode(self._filter_by_session(session_guid, dtos)))

    @staticmethod
    def _filter_by_session(session_guid: str, dtos: list) -> list:
        return [dto for dto in dtos if dto.session_guid == session_guid]

    def _poll(
        self,
        session_guid: str,
        command: ScoringProgramDataConnectorCommands,
        expected_data_type: DataConnectorResponseData,
        dto_class,
    ) -> list:
        response = self._send(session_guid, command, "")
        if response.data_type != expected_data_type:
            return []
        if response.serialized_data is None or response.serialized_data.strip() == "":
            return []
        try:
            items = json.loads(response.serialized_data)
        except json.JSONDecodeError:
            return []
        if not isinstance(items, list):
            return []
        dtos = [dto_class.from_dict(item) for item in items]
        if dtos:
            self._last_queue_item_ids[int(expected_data_type)] = response.last_queue_item_id
        return dtos

    def _error_response(
        self,
        command: ScoringProgramDataConnectorCommands,
        error_type: ErrorType,
        message: str,
    ) -> ScoringProgramResponse:
        response = ScoringProgramResponse()
        response.request_command = command
        response.data_type = DataConnectorResponseData.Error
        response.error_type = error_type
        response.serialized_data = json.dumps(message)
        return response
