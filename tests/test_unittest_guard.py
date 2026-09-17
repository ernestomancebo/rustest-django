import textwrap
from pathlib import Path

from _helpers import run_rustest


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
