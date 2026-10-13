from __future__ import annotations

import os
from contextlib import nullcontext
from typing import Any

from rustest import FixtureRequest, fixture

from rustest_django import _bootstrap, django_compat
from rustest_django._errors import _message
from rustest_django.blocker import DjangoDbBlocker
from rustest_django.rustest_compat import requested_fixtures


class _DjangoDbContext:
    """Per-test flags inferred from the requested fixture closure.

    Flag fixtures also record dynamic requests. Repeated requests preserve the
    established isolation; a late request requiring a stronger mode fails
    explicitly instead of discarding data created during fixture setup.
    """

    def __init__(self) -> None:
        self.requested = False
        self.live_server = False
        self.transaction = False
        self.reset_sequences = False
        self.serialized_rollback = False
        self._built = False

    def _require_not_built(self, fixture_name: str) -> None:
        if self._built:
            raise RuntimeError(
                f"'{fixture_name}' was requested after database isolation had "
                "already been built for this test. Request it as a plain "
                "parameter of the test function, not from inside another fixture."
            )

    def request_db(self) -> None:
        if self._built and self.requested:
            return
        self._require_not_built("db")
        self.requested = True

    def request_transactional(self) -> None:
        if self._built and self.transaction:
            return
        self._require_not_built("transactional_db")
        self.requested = True
        self.transaction = True

    def request_reset_sequences(self) -> None:
        if self._built and self.reset_sequences:
            return
        self._require_not_built("django_db_reset_sequences")
        self.requested = True
        self.transaction = True
        self.reset_sequences = True

    def request_serialized_rollback(self) -> None:
        if self._built and self.serialized_rollback:
            return
        self._require_not_built("django_db_serialized_rollback")
        self.requested = True
        self.serialized_rollback = True


@fixture
def django_db_serialized_rollback(_django_db_context: _DjangoDbContext) -> None:
    _django_db_context.request_serialized_rollback()


@fixture
def _django_db_context(request: FixtureRequest) -> _DjangoDbContext:
    context = _DjangoDbContext()
    names = requested_fixtures(request)
    context.live_server = "live_server" in names
    context.transaction = context.live_server or "transactional_db" in names
    context.reset_sequences = "django_db_reset_sequences" in names
    context.serialized_rollback = "django_db_serialized_rollback" in names
    context.requested = bool(
        names.intersection(
            {
                "db",
                "transactional_db",
                "django_db_reset_sequences",
                "django_db_serialized_rollback",
                "live_server",
            }
        )
    )
    return context


@fixture
def db(_django_db_context: _DjangoDbContext) -> None:
    _django_db_context.request_db()


@fixture
def transactional_db(_django_db_context: _DjangoDbContext) -> None:
    _django_db_context.request_transactional()


@fixture
def django_db_reset_sequences(_django_db_context: _DjangoDbContext) -> None:
    _django_db_context.request_reset_sequences()


_session_blocker = DjangoDbBlocker()
_session_blocker.block()


@fixture(scope="session")
def django_db_blocker() -> DjangoDbBlocker:
    return _session_blocker


def _resolved(attr: str, default: Any) -> Any:
    config = _bootstrap.resolved_config
    return getattr(config, attr) if config is not None else default


@fixture(scope="session")
def django_db_keepdb() -> bool:
    return _resolved("reuse_db", False)


@fixture(scope="session")
def django_db_createdb() -> bool:
    return _resolved("create_db", False)


@fixture(scope="session")
def django_db_use_migrations() -> bool:
    return _resolved("migrations", True)


def _suffix_test_databases(suffix: str) -> None:
    from django.conf import settings

    for database in settings.DATABASES.values():
        test_settings = database.get("TEST", {})
        if test_settings.get("MIRROR"):
            continue
        name = test_settings.get("NAME")
        sqlite = database["ENGINE"] == "django.db.backends.sqlite3"
        if not name:
            if sqlite:
                continue
            name = f"test_{database['NAME']}"
        if sqlite and (name == ":memory:" or "mode=memory" in str(name)):
            continue
        database.setdefault("TEST", {})["NAME"] = f"{name}_{suffix}"


@fixture(scope="session")
def django_db_modify_db_settings_tox_suffix() -> None:
    suffix = os.environ.get("TOX_PARALLEL_ENV")
    if suffix:
        _suffix_test_databases(suffix)


@fixture(scope="session")
def django_db_modify_db_settings_xdist_suffix() -> None:
    # rustest has no public worker ID. External process launchers can supply
    # one explicitly; xdist's environment variable is accepted for migration.
    suffix = os.environ.get("RUSTEST_DJANGO_DB_SUFFIX") or os.environ.get(
        "PYTEST_XDIST_WORKER"
    )
    if suffix:
        _suffix_test_databases(suffix)


@fixture(scope="session")
def django_db_modify_db_settings_parallel_suffix(
    django_db_modify_db_settings_tox_suffix: None,
    django_db_modify_db_settings_xdist_suffix: None,
) -> None:
    pass


@fixture(scope="session")
def django_db_modify_db_settings(
    django_db_modify_db_settings_parallel_suffix: None,
) -> None:
    pass


def _disable_migrations() -> None:
    from django.conf import settings
    from django.core.management.commands import migrate

    class DisableMigrations:
        def __contains__(self, item: str) -> bool:
            return True

        def __getitem__(self, item: str) -> None:
            return None

    settings.MIGRATION_MODULES = DisableMigrations()

    class MigrateSilentCommand(migrate.Command):
        def handle(self, *args: Any, **kwargs: Any) -> Any:
            kwargs["verbosity"] = 0
            return super().handle(*args, **kwargs)

    migrate.Command = MigrateSilentCommand  # ty: ignore[invalid-assignment]


@fixture(scope="session")
def django_db_setup(
    django_db_blocker: DjangoDbBlocker,
    django_db_use_migrations: bool,
    django_db_keepdb: bool,
    django_db_createdb: bool,
    django_db_modify_db_settings: None,
):
    from django.test.utils import setup_databases, teardown_databases

    if not django_db_use_migrations:
        _disable_migrations()

    setup_kwargs = {}
    if django_db_keepdb and not django_db_createdb:
        setup_kwargs["keepdb"] = True

    with django_db_blocker.unblock():
        db_cfg = setup_databases(verbosity=0, interactive=False, **setup_kwargs)

    yield

    if not django_db_keepdb:
        with django_db_blocker.unblock():
            teardown_databases(db_cfg, verbosity=0)


def _django_db_arguments(
    transaction: bool = False,
    reset_sequences: bool = False,
    databases: list[str] | None = None,
    serialized_rollback: bool = False,
    available_apps: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "transaction": transaction,
        "reset_sequences": reset_sequences,
        "databases": databases,
        "serialized_rollback": serialized_rollback,
        "available_apps": available_apps,
    }


@fixture(autouse=True)
def _django_db_isolation(
    request: FixtureRequest,
    _django_db_context: _DjangoDbContext,
    django_db_blocker: DjangoDbBlocker,
):
    marker = request.node.get_closest_marker("django_db")
    try:
        marker_kwargs = (
            _django_db_arguments(*marker.args, **marker.kwargs)
            if marker is not None
            else {}
        )
    except TypeError as exc:
        raise TypeError(_message(f"invalid @mark.django_db arguments: {exc}")) from exc

    if not _django_db_context.requested and marker is None:
        yield
        return

    request.getfixturevalue("django_db_setup")
    _django_db_context._built = True
    _reset_sequences = _django_db_context.reset_sequences or marker_kwargs.get(
        "reset_sequences", False
    )
    _serialized_rollback = _django_db_context.serialized_rollback or marker_kwargs.get(
        "serialized_rollback", False
    )
    _databases = marker_kwargs.get("databases")
    _available_apps = marker_kwargs.get("available_apps")
    transactional = (
        _django_db_context.transaction
        or _reset_sequences
        or marker_kwargs.get("transaction", False)
    )

    with django_db_blocker.unblock():
        test_case_class = django_compat.build_test_case_class(
            transactional=transactional,
            reset_sequences=_reset_sequences,
            serialized_rollback=_serialized_rollback,
            databases=_databases,
            available_apps=_available_apps,
        )
        test_case = django_compat.pre_setup(test_case_class)

        from django.test.utils import modify_settings

        config = _bootstrap.resolved_config
        settings_context = (
            modify_settings(
                ALLOWED_HOSTS={
                    "append": getattr(config, "live_server_host", "localhost")
                }
            )
            if _django_db_context.live_server
            else nullcontext()
        )
        try:
            with settings_context:
                yield
        finally:
            django_compat.post_teardown(test_case, test_case_class)
