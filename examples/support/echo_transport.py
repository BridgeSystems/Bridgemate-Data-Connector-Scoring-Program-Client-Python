"""Wire-tracing transport decorator for the getting-started sample. See EchoTransport."""

import json

from bridgemate_dataconnector import HttpTransport


class EchoTransport(HttpTransport):
    """Decorates another HttpTransport and echoes every request and response to the console,
    with the nested SerializedData expanded, so you can trace the wire traffic of the
    DataConnectorClient without a debugger.
    """

    def __init__(self, inner: HttpTransport):
        self._inner = inner
        self.enabled = True

    def get(self, url: str) -> str:
        self._echo_line(f">> GET  {url}")
        body = self._inner.get(url)
        self._echo_line(f"<< {body}")
        return body

    def post(self, url: str, json_body: str) -> str:
        self._echo_line(f">> POST {url}")
        self._echo_json(json_body)
        body = self._inner.post(url, json_body)
        self._echo_line("<<")
        self._echo_json(body)
        return body

    def _echo_line(self, line: str):
        if self.enabled:
            print(f"\033[36m{line}\033[0m")

    def _echo_json(self, body: str):
        """Pretty-prints an envelope. The SerializedData property is itself a JSON string
        ("double serialization"); expand it so the payload is readable.
        """
        if not self.enabled:
            return
        decoded = json.loads(body)
        if isinstance(decoded, dict) and decoded.get("SerializedData"):
            decoded["SerializedData"] = json.loads(decoded["SerializedData"])
        self._echo_line(json.dumps(decoded, indent=4))
