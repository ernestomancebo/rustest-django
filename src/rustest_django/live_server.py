from __future__ import annotations

from contextlib import ExitStack

from rustest import FixtureRequest, fixture

from rustest_django import _bootstrap, django_compat


class LiveServer:
    """A real HTTP server, started when its URL is first used."""

    def __init__(self, request: FixtureRequest, host: str, port: int) -> None:
        self._request = request
        self._host = host
        self._port = port
        self._url: str | None = None
        self._stack = ExitStack()

    @property
    def url(self) -> str:
        if self._url is None:
            self._request.getfixturevalue("_django_db_isolation")
            try:
                port = self._stack.enter_context(
                    django_compat.running_live_server(self._host, self._port)
                )
                self._url = f"http://{self._host}:{port}"
            except BaseException:
                self.stop()
                raise
        return self._url

    def stop(self) -> None:
        self._stack.close()

    def __str__(self) -> str:
        return self.url

    def __add__(self, other: str) -> str:
        return self.url + other

    def __radd__(self, other: str) -> str:
        return other + self.url


@fixture(scope="session")
def live_server(request: FixtureRequest, django_db_setup: None):
    config = _bootstrap.resolved_config
    server = LiveServer(
        request,
        getattr(config, "live_server_host", "localhost"),
        getattr(config, "live_server_port", 0),
    )
    try:
        yield server
    finally:
        server.stop()
