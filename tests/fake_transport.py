"""A scripted HttpTransport for the unit tests: records every call and replays queued
responses (or raises queued TransportExceptions), mirroring the FakeTransport of the PHP
and Java ports.
"""

from bridgemate_dataconnector import HttpTransport, TransportException


class FakeTransport(HttpTransport):
    def __init__(self):
        # Every call as a (url, body) tuple; body is None for GET.
        self.calls: list[tuple[str, str | None]] = []
        # Scripted responses, consumed front to back: a str body or a TransportException to raise.
        self.responses: list = []

    def get(self, url: str) -> str:
        return self._record(url, None)

    def post(self, url: str, json_body: str) -> str:
        return self._record(url, json_body)

    def _record(self, url: str, body: str | None) -> str:
        self.calls.append((url, body))
        response = self.responses.pop(0) if self.responses else TransportException("No scripted response.")
        if isinstance(response, TransportException):
            raise response
        return response
