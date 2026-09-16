from __future__ import annotations

from rustest import FixtureRequest, fixture

from rustest_django import django_compat
from rustest_django.blocker import DjangoDbBlocker


class _DjangoDbContext:
    """Per-test flags, replacing what pytest-django reads off ``request.fixturenames``.

    rustest has no fixture-closure introspection, so ``db``/``transactional_db``
    set flags here instead. They rely on rustest resolving explicit test
    parameters before autouse fixtures, so `_django_db_isolation` (autouse)
    always sees the flags by the time it runs.
    """

    def __init__(self) -> None:
        self.requested = False
        self.transaction = False
        self.reset_sequences = False
        self._built = False

    def _require_not_built(self, fixture_name: str) -> None:
        if self._built:
            raise RuntimeError(
                f"'{fixture_name}' was requested after database isolation had "
                "already been built for this test. Request it as a plain "
                "parameter of the test function, not from inside another fixture."
            )

    def request_db(self) -> None:
        self._require_not_built("db")
        self.requested = True

    def request_transactional(self) -> None:
        self._require_not_built("transactional_db")
        self.requested = True
        self.transaction = True

    def request_reset_sequences(self) -> None:
        self._require_not_built("django_db_reset_sequences")
        self.requested = True
        self.transaction = True
        self.reset_sequences = True


@fixture
def _django_db_context() -> _DjangoDbContext:
    return _DjangoDbContext()


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


@fixture(scope="session")
def django_db_setup(django_db_blocker: DjangoDbBlocker):
    from django.test.utils import setup_databases, teardown_databases

    with django_db_blocker.unblock():
        db_cfg = setup_databases(verbosity=0, interactive=False)

    yield

    with django_db_blocker.unblock():
        teardown_databases(db_cfg, verbosity=0)


@fixture(autouse=True)
def _django_db_isolation(
    request: FixtureRequest,
    _django_db_context: _DjangoDbContext,
    django_db_blocker: DjangoDbBlocker,
):
    marker = request.node.get_closest_marker("django_db")
    marker_kwargs = marker.kwargs if marker is not None else {}

    if not _django_db_context.requested and marker is None:
        yield
        return

    request.getfixturevalue("django_db_setup")
    _django_db_context._built = True
    _reset_sequences = _django_db_context.reset_sequences or marker_kwargs.get(
        "reset_sequences", False
    )
    _serialized_rollback = marker_kwargs.get("serialized_rollback", False)
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

        try:
            yield
        finally:
            django_compat.post_teardown(test_case, test_case_class)
