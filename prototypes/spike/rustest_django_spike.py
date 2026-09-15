"""PROTOTYPE, throwaway. Minimal rustest fixture module standing in for rustest-django.

Loaded by the consumer's conftest via `rustest_fixtures = ["rustest_django_spike"]`.
Never imported under pytest; there pytest-django provides the same names.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tomllib
import traceback

from rustest import fixture

# --- runner options: [tool.rustest-django] in pyproject.toml, env wins ------------------


def _load_config() -> tuple[dict, pathlib.Path | None]:
    for d in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]:
        p = d / "pyproject.toml"
        if p.exists():
            cfg = tomllib.loads(p.read_text()).get("tool", {}).get("rustest-django")
            if cfg:
                return cfg, d
    return {}, None


# --- import-time bootstrap: test modules import models, so apps must be ready now -------

_BOOTSTRAP_ERROR: BaseException | None = None


def _bootstrap() -> None:
    cfg, _root = _load_config()
    sm = os.environ.get("DJANGO_SETTINGS_MODULE") or cfg.get("settings_module")
    if not sm:
        raise RuntimeError("rustest-django: no DJANGO_SETTINGS_MODULE and no [tool.rustest-django].settings_module")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", sm)
    import django

    django.setup()


try:
    _bootstrap()
except BaseException as exc:  # never raise at import: rustest swallows it silently (#3)
    _BOOTSTRAP_ERROR = exc
    print("rustest-django bootstrap failed:\n" + "".join(traceback.format_exception(exc)), file=sys.stderr)


# --- DB blocker (mirrors pytest-django DjangoDbBlocker) ---------------------------------


class _Blocker:
    def __init__(self) -> None:
        self._real = None
        self.active = False

    def _blocked(self, *a, **k):
        raise RuntimeError(
            'Database access not allowed, use the "django_db" mark, or the '
            '"db" or "transactional_db" fixtures to enable it.'
        )

    def block(self) -> None:
        from django.db.backends.base.base import BaseDatabaseWrapper

        if self._real is None:
            self._real = BaseDatabaseWrapper.ensure_connection
        BaseDatabaseWrapper.ensure_connection = self._blocked
        self.active = True

    def unblock(self) -> None:
        from django.db.backends.base.base import BaseDatabaseWrapper

        if self._real is not None:
            BaseDatabaseWrapper.ensure_connection = self._real
        self.active = False


django_db_blocker = _Blocker()


# --- session: test environment + test databases ----------------------------------------


@fixture(scope="session", autouse=True)
def django_test_environment():
    if _BOOTSTRAP_ERROR is not None:
        raise RuntimeError("rustest-django: Django bootstrap failed at import time") from _BOOTSTRAP_ERROR
    from django.test.utils import setup_test_environment, teardown_test_environment

    print("[spike] setup_test_environment")
    setup_test_environment()
    django_db_blocker.block()
    try:
        yield
    finally:
        django_db_blocker.unblock()
        teardown_test_environment()
        print("[spike] teardown_test_environment")


@fixture(scope="session")
def django_db_setup(django_test_environment):
    from django.test.utils import setup_databases, teardown_databases

    django_db_blocker.unblock()
    print("[spike] setup_databases")
    old = setup_databases(verbosity=0, interactive=False)
    django_db_blocker.block()
    try:
        yield
    finally:
        django_db_blocker.unblock()
        teardown_databases(old, verbosity=0)
        django_db_blocker.block()
        print("[spike] teardown_databases")


# --- per-test: marker -> fixture activation --------------------------------------------


@fixture(autouse=True)
def _django_db_marker(request):
    m = request.node.get_closest_marker("django_db")
    if m is None:
        return
    transaction = m.kwargs.get("transaction", m.args[0] if m.args else False)
    request.getfixturevalue("transactional_db" if transaction else "db")


def _run_testcase(case_cls):
    """TestCase-style isolation exactly as pytest-django's _django_db_helper does it."""
    django_db_blocker.unblock()
    case_cls.setUpClass()
    case = case_cls("__init__")
    case._pre_setup()
    try:
        yield
    finally:
        case._post_teardown()
        case_cls.tearDownClass()
        django_db_blocker.block()


@fixture
def db(request, django_db_setup):
    from django.test import TestCase

    class _Case(TestCase):
        pass

    yield from _run_testcase(_Case)


@fixture
def transactional_db(request, django_db_setup):
    from django.test import TransactionTestCase

    class _Case(TransactionTestCase):
        pass

    yield from _run_testcase(_Case)


@fixture
def client():
    from django.test import Client

    return Client()


@fixture
def rf():
    from django.test import RequestFactory

    return RequestFactory()
