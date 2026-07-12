"""Transport error type. See TransportException."""


class TransportException(Exception):
    """Raised by an HttpTransport when the request could not be completed (connection failure,
    timeout or a non-2xx status). The DataConnectorClient catches it and retries; it never
    escapes to calling code.
    """

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        # The http status code when the request completed with a non-2xx status, else None.
        self.status_code = status_code
