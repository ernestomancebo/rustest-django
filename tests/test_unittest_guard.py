import textwrap
from pathlib import Path

from _helpers import run_rustest, temporary_module, write_django_conftest


def test_unittest_style_testcase_fails_loudly(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [tool.rustest-django]
            settings_module = "settings"
            """
        )
    )
    (tmp_path / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (tmp_path / "settings.py").write_text(
        textwrap.dedent(
            """
            DATABASES = {
                "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
            }
            USE_TZ = True
            """
        )
    )
    (tmp_path / "test_consumer.py").write_text(
        textwrap.dedent(
            """
            import django.test


            class MyLegacyTests(django.test.SimpleTestCase):
                def test_something(self):
                    self.assertEqual(1, 1)
            """
        )
    )

    result = run_rustest(tmp_path)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "1 failed" in result.stderr
    assert "MyLegacyTests" in result.stderr
    assert "rustest-django: " in result.stderr
    assert "unsupported in rustest-django v1" in result.stderr
    assert "Use plain functions with the db/transactional_db fixtures" in result.stderr


def test_plain_function_test_is_unaffected(tmp_path: Path) -> None:
    (tmp_path / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (tmp_path / "test_consumer.py").write_text(
        "def test_plain_math():\n    assert 1 + 1 == 2\n"
    )

    result = run_rustest(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stderr


def test_plain_class_tests_are_not_failed_by_the_guard(tmp_path: Path) -> None:
    write_django_conftest(tmp_path)
    (tmp_path / "test_consumer.py").write_text(
        textwrap.dedent(
            """
            from rustest_django import django_db

            @django_db
            class TestGrouped:
                def test_one(self):
                    assert True

                def test_two(self):
                    assert True
            """
        )
    )

    result = run_rustest(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stderr


def test_same_file_name_in_two_directories_resolves_to_the_right_class(
    tmp_path: Path,
) -> None:
    write_django_conftest(tmp_path)
    for directory, body in (
        ("plain", "class TestShared:\n    def test_it(self):\n        assert True\n"),
        (
            "legacy",
            "import django.test\n\n"
            "class TestShared(django.test.SimpleTestCase):\n"
            "    def test_it(self):\n        assert True\n",
        ),
    ):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "__init__.py").write_text("")
        (tmp_path / directory / "test_shared.py").write_text(body)

    result = run_rustest(tmp_path)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "1 passed" in result.stderr
    assert "1 failed" in result.stderr
    assert "legacy.test_shared.TestShared" in result.stderr


def test_module_imported_after_earlier_lookups_is_resolved(tmp_path: Path) -> None:
    import importlib.util
    from types import SimpleNamespace

    from rustest_django.unittest_guard import _resolve_test_class

    source = tmp_path / "late_guard_module.py"
    source.write_text("class LateTests:\n    pass\n")
    node = SimpleNamespace(
        name="LateTests::test_it", nodeid=f"{source}::LateTests::test_it"
    )
    assert _resolve_test_class(node) is None

    spec = importlib.util.spec_from_file_location("late_guard_module", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with temporary_module(module):
        assert _resolve_test_class(node) is module.LateTests
