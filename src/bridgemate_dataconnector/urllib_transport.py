"""Standard library http implementation. See UrllibTransport."""

import urllib.error
import urllib.request

from .http_transport import HttpTransport
from .transport_exception import TransportException


class UrllibTransport(HttpTransport):
    """urllib.request implementation of HttpTransport, so the package has no dependencies
    outside the standard library.

    urllib exposes a single timeout that covers connecting and reading. The .NET client uses
    10 seconds to connect and 100 seconds for the whole request; with one knob we keep the
    100 second total, which behaves the same for every practical purpose (a dead host on a
    LAN fails the TCP connect long before that).
    """

    def __init__(self, timeout_seconds: float = 100.0):
        self._timeout_seconds = timeout_seconds
        # The data connector lives on localhost or the LAN: a system proxy without a localhost
        # bypass hijacks the request (503). The default opener honors proxy environment variables
        # and, on Windows, the registry proxy settings, so use an opener with proxying disabled.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(self, url: str) -> str:
        return self._execute(url, None)

    def post(self, url: str, json_body: str) -> str:
        return self._execute(url, json_body)

    def _execute(self, url: str, json_body: str | None) -> str:
        headers = {}
        data = None
        method = "GET"
        if json_body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
            data = json_body.encode("utf-8")
            method = "POST"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self._timeout_seconds) as response:
                # urlopen only returns 2xx responses; anything else raises HTTPError below.
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise TransportException(
                f"Request to '{url}' returned status {error.code}.", status_code=error.code
            ) from error
        except urllib.error.URLError as error:
            raise TransportException(f"Request to '{url}' failed: {error.reason}") from error
        except TimeoutError as error:
            raise TransportException(f"Request to '{url}' timed out.") from error
