"""Scoring program client for the Bridgemate Data Connector over http.

The hand-written runtime lives in this package; the generated wire-format types live in the
dto subpackage (import them with: from bridgemate_dataconnector.dto import InitDTO).
"""

from .client import DataConnectorClient
from .http_transport import HttpTransport
from .transport_exception import TransportException
from .urllib_transport import UrllibTransport

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
]
