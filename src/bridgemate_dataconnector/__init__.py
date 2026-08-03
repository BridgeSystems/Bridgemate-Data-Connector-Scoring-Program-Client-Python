"""Scoring program client for the Bridgemate Data Connector over http.

The hand-written runtime lives in this package; the generated wire-format types live in the
dto subpackage (import them with: from bridgemate_dataconnector.dto import InitDTO).
"""

from .client import DataConnectorClient
from .http_transport import HttpTransport
from .transport_exception import TransportException
from .urllib_transport import UrllibTransport
from .validation import (
    validate_bridgemate2_settings_dto,
    validate_bridgemate3_settings_dto,
    validate_continue_dto,
    validate_handrecord_dto,
    validate_init_dto,
    validate_participation_dto,
    validate_player_data_dto,
    validate_result_dto,
    validate_round_dto,
    validate_scoring_group_dto,
    validate_section_dto,
    validate_section_update_dto,
    validate_session_dto,
    validate_table_dto,
    validate_td_call_dto,
)

try:
    from importlib.metadata import version

    __version__ = version("bridgemate-dataconnector-client")
except Exception:  # pragma: no cover - only hit when running from a plain checkout.
    __version__ = "0.0.0"

__all__ = [
    "DataConnectorClient",
    "HttpTransport",
    "TransportException",
    "UrllibTransport",
    "__version__",
    "validate_bridgemate2_settings_dto",
    "validate_bridgemate3_settings_dto",
    "validate_continue_dto",
    "validate_handrecord_dto",
    "validate_init_dto",
    "validate_participation_dto",
    "validate_player_data_dto",
    "validate_result_dto",
    "validate_round_dto",
    "validate_scoring_group_dto",
    "validate_section_dto",
    "validate_section_update_dto",
    "validate_session_dto",
    "validate_table_dto",
    "validate_td_call_dto",
]
