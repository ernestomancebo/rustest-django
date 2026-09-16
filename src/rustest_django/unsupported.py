from __future__ import annotations

from rustest import FixtureRequest, fixture


def _unsupported(name: str) -> None:
    raise RuntimeError(
        f"'{name}' is unsupported in rustest-django v1. It exists so a "
        "migrated test naming it fails loudly instead of silently losing "
        "coverage."
    )


@fixture
def live_server() -> None:
    _unsupported("live_server")


@fixture
def django_db_serialized_rollback() -> None:
    _unsupported("django_db_serialized_rollback")


@fixture
def django_isolated_apps() -> None:
    _unsupported("django_isolated_apps")


@fixture(autouse=True)
def _unsupported_marker_guard(request: FixtureRequest) -> None:
    for marker_name in ("urls", "ignore_template_errors"):
        if request.node.get_closest_marker(marker_name) is not None:
            _unsupported(f"@mark.{marker_name}")