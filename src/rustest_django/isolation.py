from __future__ import annotations

import django.test
from rustest import FixtureRequest, fixture

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


@fixture
def _django_db_context() -> _DjangoDbContext:
    return _DjangoDbContext()


@fixture
def db(_django_db_context: _DjangoDbContext) -> None:
    _django_db_context.request_db()


@fixture
def transactional_db(_django_db_context: _DjangoDbContext) -> None:
    _django_db_context.request_transactional()


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
    django_db_setup: None,
    django_db_blocker: DjangoDbBlocker,
):
    if not _django_db_context.requested:
        yield
        return

    _django_db_context._built = True
    transactional = _django_db_context.transaction

    with django_db_blocker.unblock():
        test_case_class = (
            django.test.TransactionTestCase if transactional else django.test.TestCase
        )

        class _RustestDjangoTestCase(test_case_class):
            if not transactional:

                @classmethod
                def setUpClass(cls) -> None:
                    super(django.test.TestCase, cls).setUpClass()

                @classmethod
                def tearDownClass(cls) -> None:
                    super(django.test.TestCase, cls).tearDownClass()

        _RustestDjangoTestCase.setUpClass()
        test_case = _RustestDjangoTestCase(methodName="__init__")
        pre_setup_ran_eagerly = getattr(
            _RustestDjangoTestCase, "_pre_setup_ran_eagerly", False
        )
        if not pre_setup_ran_eagerly:
            test_case._pre_setup()

        yield

        test_case._post_teardown()
        _RustestDjangoTestCase.tearDownClass()
        _RustestDjangoTestCase.doClassCleanups()
