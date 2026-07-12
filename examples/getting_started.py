"""Getting-started sample for the Bridgemate Data Connector Python client.

Interactive:  python examples/getting_started.py
Unattended:   python examples/getting_started.py --scenario

Options: --base-address http://host:5079  --club-id ...  --licence-key ...  --no-trace

The "initialize event" action instructs the Data Connector to START Bridgemate Control
Software and create a small test event (1 section, 2 tables, 3 rounds). Watch BCS open,
enter a result there (or on a Bridgemate), then use the poll actions here to receive it.
"""

import argparse
import json
import os
import platform
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Prefer the checkout next to this sample over an installed copy, so the sample (and the
# VS Code launch configurations) work on a plain git clone without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bridgemate_dataconnector import DataConnectorClient, UrllibTransport  # noqa: E402
from bridgemate_dataconnector.dto import (  # noqa: E402
    ContinueDTO,
    DataConnectorResponseData,
    InitDTO,
    ParticipationDTO,
    PlayerDataDTO,
    ResultDTO,
    ScoringProgramResponse,
    TableDirection,
)
from support.echo_transport import EchoTransport  # noqa: E402

EXAMPLES_DIR = Path(__file__).resolve().parent
STATE_FILE = EXAMPLES_DIR / ".state.json"

# ------------------------------------------------------------------------------------------
# Actions. Each one is a plain function of the client, so this file doubles as sample code.
# ------------------------------------------------------------------------------------------


def connect_and_ping(client: DataConnectorClient):
    report("Connect", client.connect())
    report("Ping", client.ping())


def initialize_event(client: DataConnectorClient) -> ScoringProgramResponse:
    """Creates a fresh event from the template: new event/session guids and today's date.

    Commands = 7 tells the Data Connector to start BCS (1), reset (2) and start reading (4).
    """
    template = (EXAMPLES_DIR / "data" / "init-template.json").read_text(encoding="utf-8")
    session_guid = new_guid()
    event_guid = new_guid()
    data = json.loads(template.replace("REPLACED-AT-RUNTIME", session_guid))
    now = datetime.now()
    data["EventGuid"] = event_guid
    data["Sessions"][0]["EventGuid"] = event_guid
    data["Sessions"][0]["Year"] = now.year
    data["Sessions"][0]["Month"] = now.month
    data["Sessions"][0]["Day"] = now.day
    data["Sessions"][0]["Hour"] = now.hour
    data["Sessions"][0]["Minute"] = now.minute

    init_dto = InitDTO.from_dict(data)
    init_dto.player_data = load_player_data(session_guid)
    init_dto.participations = load_participations(session_guid)

    response = client.initialize(init_dto)
    save_state({"sessionGuid": session_guid, "eventGuid": event_guid})
    print(f"Session guid: {session_guid} (saved to .state.json)")
    return response


def continue_event(client: DataConnectorClient) -> ScoringProgramResponse:
    continue_dto = ContinueDTO()
    continue_dto.event_guid = state()["eventGuid"]
    # Unlike InitDTO, ContinueDTO must not carry the Reset flag (2): only start BCS (1),
    # start reading (4) and optionally clear data (128), minimize, auto-shutdown or debug logging.
    continue_dto.commands = 5
    return client.continue_event(continue_dto)


def send_player_data(client: DataConnectorClient) -> ScoringProgramResponse:
    session_guid = state()["sessionGuid"]
    return client.send_player_data(session_guid, load_player_data(session_guid))


def send_one_result(client: DataConnectorClient) -> ScoringProgramResponse:
    """Uploads one board result: table 1, round 1, board 1 — 1♣ by North, 7 tricks, lead ♣A."""
    session_guid = state()["sessionGuid"]
    result = ResultDTO()
    result.session_guid = session_guid
    result.section_letters = "A"
    result.table_number = 1
    result.round_number = 1
    result.board_number = 1
    result.scoring_direction = ResultDTO.ScoringDirection_NSEW
    result.pair_north_south = 1
    result.pair_east_west = 2
    result.declaring_pair = 1
    result.declarer_direction = ResultDTO.Direction_North
    result.level = 1
    result.denomination = ResultDTO.Denomination_Clubs
    result.stake = ResultDTO.Stake_Normal
    result.total_tricks = 7
    result.lead_card_rank = 14
    result.lead_card_suit = 1
    return client.send_results(session_guid, [result])


def poll_queue(client: DataConnectorClient, data_type: DataConnectorResponseData, poll_all: bool):
    session_guid = state()["sessionGuid"]
    polls = {
        DataConnectorResponseData.Results: client.poll_for_results,
        DataConnectorResponseData.PlayerData: client.poll_for_player_data,
        DataConnectorResponseData.Participations: client.poll_for_participations,
        DataConnectorResponseData.Handrecords: client.poll_for_handrecords,
        DataConnectorResponseData.TdCalls: client.poll_for_td_calls,
    }
    items = polls[data_type](session_guid, poll_all)
    print(f"Polled {data_type.name}: {len(items)} item(s)")
    for index, item in enumerate(items):
        print(f"  #{index + 1}")
        print(indent(indent(json.dumps(item.to_dict(), indent=4))))
    if items:
        print(
            f"Last queue item id: {client.get_last_queue_item_id(data_type)}"
            " — use 'accept' so they are not sent again."
        )


def accept_queue(client: DataConnectorClient, data_type: DataConnectorResponseData):
    report(f"Accept {data_type.name}", client.accept_queue_data(state()["sessionGuid"], data_type))


# ------------------------------------------------------------------------------------------
# Scenario mode: the whole flow in one run. Exit code 0 when every step succeeded.
# ------------------------------------------------------------------------------------------


def run_scenario(client: DataConnectorClient) -> int:
    ok = True

    def check(step: str, response: ScoringProgramResponse):
        nonlocal ok
        success = response.data_type != DataConnectorResponseData.Error
        ok = ok and success
        print(f"{step:<20} {'OK' if success else 'FAILED: ' + response.error_type.name}")

    check("Connect", client.connect())
    check("Ping", client.ping())
    check("InitializeEvent", initialize_event(client))
    check("PutPlayerData", send_player_data(client))
    check("PutResults", send_one_result(client))
    poll_queue(client, DataConnectorResponseData.Results, False)
    print("SCENARIO OK" if ok else "SCENARIO FAILED")
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------
# Interactive menu
# ------------------------------------------------------------------------------------------

MENU = """
 1  Connect + ping
 2  Initialize event (starts BCS, creates a fresh test event)
 3  Continue event (re-open the event from .state.json)
 4  Send player data
 5  Send a board result (A1, round 1, board 1)
 6  Poll results            7  Accept results
 8  Poll player data        9  Accept player data
10  Poll participations    11  Accept participations
12  Poll handrecords       13  Accept handrecords
14  Poll TD calls          15  Accept TD calls
16  Toggle 'poll all' (currently: {poll_all})
17  Toggle wire trace (currently: {trace})
 0  Quit
"""


def run_menu(client: DataConnectorClient, trace: EchoTransport):
    poll_all = False
    while True:
        print(
            MENU.format(
                poll_all="all items" if poll_all else "new items only",
                trace="on" if trace.enabled else "off",
            )
        )
        choice = input("Choice: ").strip()
        try:
            if choice == "1":
                connect_and_ping(client)
            elif choice == "2":
                report("InitializeEvent", initialize_event(client))
            elif choice == "3":
                report("ContinueEvent", continue_event(client))
            elif choice == "4":
                report("PutPlayerData", send_player_data(client))
            elif choice == "5":
                report("PutResults", send_one_result(client))
            elif choice == "6":
                poll_queue(client, DataConnectorResponseData.Results, poll_all)
            elif choice == "7":
                accept_queue(client, DataConnectorResponseData.Results)
            elif choice == "8":
                poll_queue(client, DataConnectorResponseData.PlayerData, poll_all)
            elif choice == "9":
                accept_queue(client, DataConnectorResponseData.PlayerData)
            elif choice == "10":
                poll_queue(client, DataConnectorResponseData.Participations, poll_all)
            elif choice == "11":
                accept_queue(client, DataConnectorResponseData.Participations)
            elif choice == "12":
                poll_queue(client, DataConnectorResponseData.Handrecords, poll_all)
            elif choice == "13":
                accept_queue(client, DataConnectorResponseData.Handrecords)
            elif choice == "14":
                poll_queue(client, DataConnectorResponseData.TdCalls, poll_all)
            elif choice == "15":
                accept_queue(client, DataConnectorResponseData.TdCalls)
            elif choice == "16":
                poll_all = not poll_all
            elif choice == "17":
                trace.enabled = not trace.enabled
            elif choice == "0":
                return
            else:
                print("Unknown choice.")
        except RuntimeError as error:
            print(f"Error: {error}")


# ------------------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------------------


def report(action: str, response: ScoringProgramResponse):
    print(f"{action} -> DataType={response.data_type.name} ErrorType={response.error_type.name}")
    print(indent(pretty_data(response.serialized_data)))


def pretty_data(serialized_data: str | None) -> str:
    """Renders the (JSON string) payload of a response in full, pretty-printed. \\r\\n sequences
    inside message strings become real line breaks so validation messages read naturally.
    """
    if serialized_data is None or serialized_data.strip() == "":
        return "(no data)"
    decoded = json.loads(serialized_data)
    if isinstance(decoded, str):
        return decoded.replace("\r\n", "\n").replace("\r", "\n")
    return json.dumps(decoded, indent=4)


def indent(text: str) -> str:
    return "  " + text.replace("\n", "\n  ")


def new_guid() -> str:
    return uuid.uuid4().hex.upper()


def load_player_data(session_guid: str) -> list:
    players = json.loads((EXAMPLES_DIR / "data" / "players.json").read_text(encoding="utf-8"))
    player_data = []
    for player in players:
        dto = PlayerDataDTO()
        dto.session_guid = session_guid
        dto.player_number = player["PlayerNumber"]
        dto.first_name = player["FirstName"]
        dto.last_name = player["LastName"]
        dto.country_code = player["CountryCode"]
        player_data.append(dto)
    return player_data


def load_participations(session_guid: str) -> list:
    """Round-1 seating for the players in players.json."""
    players = json.loads((EXAMPLES_DIR / "data" / "players.json").read_text(encoding="utf-8"))
    participations = []
    for player in players:
        dto = ParticipationDTO()
        dto.session_guid = session_guid
        dto.section_letters = player["SectionLetters"]
        dto.table_number = player["TableNumber"]
        dto.direction = TableDirection(player["Direction"])
        dto.round_number = 1
        dto.player_number = player["PlayerNumber"]
        participations.append(dto)
    return participations


def state() -> dict:
    if not STATE_FILE.exists():
        raise RuntimeError('No event yet: run "Initialize event" first.')
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(new_state: dict):
    STATE_FILE.write_text(json.dumps(new_state, indent=4), encoding="utf-8")


# ------------------------------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------------------------------


def main() -> int:
    os.system("")  # Enables ANSI colors in the legacy Windows console; a no-op elsewhere.
    print("=== Bridgemate Data Connector getting-started sample - Python client ===")
    print(f"Running on Python {platform.python_version()} ({platform.system()})")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", action="store_true", help="run the whole flow unattended")
    parser.add_argument("--base-address", help="Data Connector address, e.g. http://192.168.1.50:5079")
    parser.add_argument("--club-id", default="", help="club id for http communication")
    parser.add_argument("--licence-key", default="", help="licence key for http communication")
    parser.add_argument("--no-trace", action="store_true", help="disable the wire trace")
    args = parser.parse_args()

    trace = EchoTransport(UrllibTransport())
    trace.enabled = not args.no_trace
    client = DataConnectorClient(
        club_id=args.club_id,
        licence_key=args.licence_key,
        base_address=args.base_address,
        transport=trace,
    )
    print(f"Data Connector address: {client.base_address}")

    if args.scenario:
        return run_scenario(client)
    run_menu(client, trace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
