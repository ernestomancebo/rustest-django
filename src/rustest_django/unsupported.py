from __future__ import annotations

from rustest import FixtureRequest, fixture

from rustest_django._errors import _message


def _unsupported(name: str, fix: str | None = None) -> None:
    body = (
        f"'{name}' is unsupported in rustest-django v1. It exists so a "
        "migrated test naming it fails loudly instead of silently losing "
        "coverage."
    )
    if fix:
        body = f"{body} {fix}"
    raise RuntimeError(_message(body))


@fixture
def live_server() -> None:
    _unsupported("live_server")


@fixture
def django_db_serialized_rollback() -> None:
    _unsupported(
        "django_db_serialized_rollback",
        "If migration-loaded data is disappearing after a transactional_db "
        "test, try db instead: it wraps the test in a transaction rather "
        "than truncating tables, so that data survives.",
    )


@fixture
def django_isolated_apps() -> None:
    _unsupported("django_isolated_apps")


@fixture(autouse=True)
def _unsupported_marker_guard(request: FixtureRequest) -> None:
    if request.node.get_closest_marker("urls") is not None:
        _unsupported(
            "@mark.urls",
            "Override settings.ROOT_URLCONF via the settings fixture instead.",
        )
    if request.node.get_closest_marker("ignore_template_errors") is not None:
        _unsupported("@mark.ignore_template_errors")
