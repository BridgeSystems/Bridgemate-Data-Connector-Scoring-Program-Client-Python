# Bridgemate Data Connector scoring program client for Python

[![PyPI](https://img.shields.io/pypi/v/bridgemate-dataconnector-client)](https://pypi.org/project/bridgemate-dataconnector-client/)
[![CI](https://github.com/BridgeSystems/Bridgemate-Data-Connector-Scoring-Program-Client-Python/actions/workflows/ci.yml/badge.svg)](https://github.com/BridgeSystems/Bridgemate-Data-Connector-Scoring-Program-Client-Python/actions/workflows/ci.yml)

Python client for scoring programs to communicate with the **Bridgemate Data Connector** over http.
Bridgemate Control Software (BCS 5) is needed to receive, process and return data from the Data
Connector. This package is the Python counterpart of the
[.NET client](https://github.com/BridgeSystems/Bridgemate-Data-Connector-Scoring-Program-Client);
its wire format is generated from the .NET source and verified against golden fixtures, so the two
clients speak an identical protocol.

## Requirements

- Python 3.10 or later — no dependencies outside the standard library
- A reachable Bridgemate Data Connector (installed with BCS 5). When the scoring program runs on a
  different computer than BCS, enable listening on the local network in BCS and allow the port
  (default 5079) through the firewall on the BCS computer.

## Installation

```
pip install bridgemate-dataconnector-client
```

## Quick start

```python
from bridgemate_dataconnector import DataConnectorClient
from bridgemate_dataconnector.dto import DataConnectorResponseData, InitDTO

# Data Connector on the same computer (port discovered through the registry, default 5079):
client = DataConnectorClient("YourClubId", "YourLicenceKey")

# Data Connector on another computer on the local network:
client = DataConnectorClient("YourClubId", "YourLicenceKey", "http://192.168.1.50:5079")

# Check the connection.
response = client.connect()

# Create an event in BCS (see the developer's guide for how to build the InitDTO).
init_dto = InitDTO()
# ... fill sessions, scoring groups, sections, tables, rounds ...
response = client.initialize(init_dto)

# Poll for new board results and accept them once processed.
results = client.poll_for_results(session_guid)
for result in results:
    ...  # store the result in your scoring program
if results:
    client.accept_queue_data(session_guid, DataConnectorResponseData.Results)
```

All methods return a `ScoringProgramResponse` (poll methods return lists of DTOs) and never raise
on communication problems: inspect `data_type`/`error_type` on the response, exactly like with the
.NET client.

### Naming

Python code uses snake_case (`result.session_guid`), while the wire format and the developer's
guide use PascalCase (`SessionGuid`). The mapping is one to one: drop the underscores and
capitalize each word. The generated `to_dict`/`from_dict` methods of every DTO spell out the
exact wire name of each field.

### Polling model

Http is stateless and the client keeps no connection open, so it fits both a long-running worker
(poll in a loop) and a web application (poll on demand during a request). The id of the last
polled queue item per data type is cached on the client instance and used by
`accept_queue_data()`; in a web application poll and accept within the same request, or track the
queue item ids yourself via `get_last_queue_item_id()`.

## Getting started sample

[examples/getting_started.py](examples/getting_started.py) is a small console application that
exercises the whole workflow against a live Data Connector — use it as a template for your own
scoring program:

```
python examples/getting_started.py               # interactive menu
python examples/getting_started.py --scenario    # unattended full flow
```

Mind that **"Initialize event" starts Bridgemate Control Software** and creates a small test
event (1 section, 2 tables, 3 rounds, 8 players). The poll queues only carry data once BCS
produces it: enter a result in BCS (or on a Bridgemate) and then poll for results here. The
sample prints every request and response envelope (wire trace, toggleable), which is the fastest
way to learn the protocol.

### Debugging in Visual Studio Code

Open this folder in VS Code and install the recommended extensions (Python + Python Debugger,
suggested automatically). Press <kbd>F5</kbd> — launch configurations for the sample and for
pytest are provided in `.vscode/launch.json`. Set a breakpoint in
`src/bridgemate_dataconnector/client.py::send_request()` to watch every envelope being built
and sent.

## Documentation

The protocol, the procedures (initializing an event, updating movements, the queues) and all DTOs
are described in the
[Bridgemate Data Connector developer's guide](https://github.com/BridgeSystems/Bridgemate-Data-Connector-Scoring-Program-Client/blob/master/Documentation/MD/index.md).
The DTO classes in `src/bridgemate_dataconnector/dto` carry the same names as the guide (fields
in snake_case, see Naming above).

## Scope

This first release covers the core workflow: `connect`/`ping`, `initialize`, `continue_event`,
`update_movement`, `update_scoring_groups`, the `send_*` methods (results, player data,
participations, handrecords, TD calls, Bridgemate 2/3 settings), the `poll_for_*` methods and
`accept_queue_data`. BCS management commands are not wrapped yet; `send_request()` is public for
anything the client does not cover.

## Compatibility

| Package version | Data Connector / BCS |
| --- | --- |
| 1.x | BCS 5.x (Data Connector with http support) |

## Development

The `src/bridgemate_dataconnector/dto` modules and `tests/fixtures` are **generated** from the
.NET client repository (`tools/DtoGenerator` there) — do not edit them by hand. The fixture tests
assert structural JSON equality with the exact bytes the .NET client produces.

```
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"    # Windows; on Linux/macOS: .venv/bin/pip
.venv\Scripts\python -m pytest
```

## Other platforms and support

The same client exists for
[.NET](https://github.com/BridgeSystems/Bridgemate-Data-Connector-Scoring-Program-Client) (the
reference implementation, including the scoring program emulator),
[PHP](https://github.com/BridgeSystems/Bridgemate-Data-Connector-Scoring-Program-Client-PHP) and
[Java](https://github.com/BridgeSystems/Bridgemate-Data-Connector-Scoring-Program-Client-Java).
Questions are welcome in the
[Discussions](https://github.com/BridgeSystems/Bridgemate-Data-Connector-Scoring-Program-Client/discussions)
of the main repository; see [SUPPORT.md](SUPPORT.md).

## License

LGPL-3.0-only, like the .NET client.
