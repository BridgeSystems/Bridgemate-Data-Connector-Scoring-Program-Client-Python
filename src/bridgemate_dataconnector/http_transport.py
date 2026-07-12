"""The http abstraction used by the DataConnectorClient. See HttpTransport."""

from abc import ABC, abstractmethod


class HttpTransport(ABC):
    """The http layer used by the DataConnectorClient. The default implementation is
    UrllibTransport; tests inject a fake and the getting-started sample wraps it in an
    EchoTransport to print every request and response.
    """

    @abstractmethod
    def get(self, url: str) -> str:
        """Performs a GET request and returns the response body.

        Raises TransportException when the request fails or returns a non-2xx status.
        """

    @abstractmethod
    def post(self, url: str, json_body: str) -> str:
        """POSTs the given JSON body with content type application/json and returns the
        response body.

        Raises TransportException when the request fails or returns a non-2xx status.
        """
