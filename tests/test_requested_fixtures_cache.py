import sys
import textwrap
import types
from pathlib import Path

from _helpers import run_rustest
from rustest import FixtureRequest, fixture
from rustest.fixture_registry import _fixture_registry, register_fixtures

from rustest_django import transactional_db
from rustest_django.rustest_compat import requested_fixtures

CONFTEST = """
import django
from django.conf import settings

settings.configure(
    SECRET_KEY="test-secret",
    INSTALLED_APPS=["django.contrib.contenttypes"],
    DATABASES={"default": {
        "ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:",
    }},
)
django.setup()
rustest_fixtures = ["rustest_django"]
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))


def _passes(project: Path) -> None:
    result = run_rustest(project)
    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert "passed" in output and "failed" not in output, output


def test_conftest_overrides_change_the_requested_closure(tmp_path: Path) -> None:
    _write(tmp_path / "conftest.py", CONFTEST)
    for directory, base in (("a", "transactional_db"), ("b", "db")):
        _write(
            tmp_path / directory / "conftest.py",
            f"""
            from rustest import fixture

            @fixture
            def consumer({base}):
                return "{base}"
            """,
        )
        _write(
            tmp_path / directory / f"test_{directory}.py",
            f"""
            from django.db import connection
            from rustest import parametrize

            @parametrize("iteration", [0, 1, 2])
            def test_mode(consumer, iteration):
                assert connection.in_atomic_block is ({base == "db"})
            """,
        )
    _passes(tmp_path)


def test_indirect_transaction_requests_are_seen_on_every_run(tmp_path: Path) -> None:
    _write(tmp_path / "conftest.py", CONFTEST)
    _write(
        tmp_path / "test_consumer.py",
        """
        from django.db import connection
        from rustest import fixture, parametrize

        @fixture
        def via_transactional(transactional_db):
            return 1

        @fixture
        def via_live_server(live_server):
            return 1

        @fixture
        def via_reset_sequences(django_db_reset_sequences):
            return 1

        @parametrize("iteration", [0, 1, 2])
        def test_transactional(via_transactional, iteration):
            assert connection.in_atomic_block is False

        @parametrize("iteration", [0, 1, 2])
        def test_live_server(via_live_server, iteration):
            assert connection.in_atomic_block is False

        @parametrize("iteration", [0, 1, 2])
        def test_reset_sequences(via_reset_sequences, iteration):
            assert connection.in_atomic_block is False
        """,
    )
    _passes(tmp_path)


def test_direct_parameters_and_fixture_requests_do_not_cross_talk(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "conftest.py", CONFTEST)
    _write(
        tmp_path / "test_consumer.py",
        """
        from django.db import connection
        from rustest import fixture, parametrize

        @fixture
        def consumer(transactional_db):
            return "fixture"

        @parametrize("consumer", ["x", "y"])
        def test_direct_value_is_not_a_request(consumer, db):
            assert connection.in_atomic_block is True

        def test_fixture_request(consumer):
            assert connection.in_atomic_block is False

        @parametrize("consumer", ["x", "y"])
        def test_direct_value_again(consumer, db):
            assert connection.in_atomic_block is True
        """,
    )
    _passes(tmp_path)


def test_autouse_fixture_in_another_module_does_not_leak(tmp_path: Path) -> None:
    _write(tmp_path / "conftest.py", CONFTEST)
    _write(
        tmp_path / "test_a.py",
        """
        from django.db import connection
        from rustest import fixture

        @fixture(autouse=True)
        def _always_transactional(transactional_db):
            return 1

        def test_a_one():
            assert connection.in_atomic_block is False

        def test_a_two():
            assert connection.in_atomic_block is False
        """,
    )
    _write(
        tmp_path / "test_b.py",
        """
        from django.db import connection

        def test_b_one(db):
            assert connection.in_atomic_block is True

        def test_b_two(db):
            assert connection.in_atomic_block is True
        """,
    )
    _passes(tmp_path)


def test_result_is_not_shared_between_calls(request: FixtureRequest) -> None:
    first = requested_fixtures(request)
    first["poison"] = object()
    first.clear()

    assert "poison" not in requested_fixtures(request)


def test_autouse_fixture_from_a_module_imported_later_is_found(
    request: FixtureRequest,
) -> None:
    before = requested_fixtures(request)
    assert "late_autouse_probe" not in before

    @fixture(autouse=True)
    def late_autouse_probe(transactional_db):
        return 1

    late = types.ModuleType("late_autouse_probe_module")
    late.late_autouse_probe = late_autouse_probe
    saved = dict(_fixture_registry)
    sys.modules[late.__name__] = late
    register_fixtures({**saved, "late_autouse_probe": late_autouse_probe})
    try:
        after = requested_fixtures(request)
    finally:
        del sys.modules[late.__name__]
        register_fixtures(saved)

    assert after["late_autouse_probe"] is late_autouse_probe
    assert after["transactional_db"] is transactional_db


def test_autouse_fixture_added_to_a_loaded_module_is_found(
    request: FixtureRequest,
) -> None:
    host = types.ModuleType("late_attribute_host")
    sys.modules[host.__name__] = host
    saved = dict(_fixture_registry)
    try:
        assert "added_later_probe" not in requested_fixtures(request)

        @fixture(autouse=True)
        def added_later_probe():
            return 1

        host.added_later_probe = added_later_probe
        register_fixtures({**saved, "added_later_probe": added_later_probe})
        assert requested_fixtures(request)["added_later_probe"] is added_later_probe
    finally:
        del sys.modules[host.__name__]
        register_fixtures(saved)
