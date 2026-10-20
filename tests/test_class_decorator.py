import textwrap
from pathlib import Path

from _helpers import run_rustest
from dbapp.models import Thing
from rustest import parametrize

from rustest_django import django_db


@django_db(transaction=True)
class TestClassDecoratedIsolation:
    @parametrize("_iteration", [0, 1])
    def test_isolates_between_calls(self, _iteration: int) -> None:
        assert Thing.objects.count() == 0

        Thing.objects.create(name="class-decorated")

        assert Thing.objects.count() == 1

    def helper_not_a_test(self) -> None:
        raise AssertionError("should never be collected or run")


def _consumer_project(project: Path, tests: str) -> None:
    (project / "conftest.py").write_text(
        textwrap.dedent(
            """
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
        )
    )
    (project / "test_consumer.py").write_text(textwrap.dedent(tests))


_DB_TEST_BODY = """
    def test_has_database_access(self):
        from django.contrib.contenttypes.models import ContentType

        assert ContentType.objects.count() >= 0
"""


def test_bare_decorator_collects_and_runs_class_with_database_access(
    tmp_path: Path,
) -> None:
    _consumer_project(
        tmp_path,
        "from rustest_django import django_db\n\n@django_db\nclass TestBare:"
        + _DB_TEST_BODY,
    )

    result = run_rustest(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stderr, result.stderr


@parametrize("call_form", ["@django_db()", "@django_db(transaction=True)"])
def test_called_decorator_still_collects_and_runs_class(
    tmp_path: Path, call_form: str
) -> None:
    _consumer_project(
        tmp_path,
        "from rustest_django import django_db\n\n"
        + call_form
        + "\nclass TestCalled:"
        + _DB_TEST_BODY,
    )

    result = run_rustest(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "1 passed" in result.stderr, result.stderr


def test_bare_decorated_name_still_refers_to_the_class() -> None:
    @django_db
    class TestBareName:
        def test_something(self) -> None: ...

    assert isinstance(TestBareName, type)
    assert TestBareName.__name__ == "TestBareName"


def test_bare_use_on_a_function_raises_type_error_saying_to_call_it() -> None:
    def not_a_class() -> None: ...

    try:
        django_db(not_a_class)
    except TypeError as error:
        assert "django_db()" in str(error)
    else:
        raise AssertionError("expected TypeError")
