import textwrap
from pathlib import Path

from _helpers import run_rustest


def _write_consumer_project(project_dir: Path) -> None:
    (project_dir / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [tool.rustest-django]
            settings_module = "settings"
            """
        )
    )
    (project_dir / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (project_dir / "settings.py").write_text(
        textwrap.dedent(
            """
            DATABASES = {
                "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
            }
            USE_TZ = True
            INSTALLED_APPS = ["consumer_app"]
            """
        )
    )
    app_dir = project_dir / "consumer_app"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("")
    (app_dir / "models.py").write_text(
        textwrap.dedent(
            """
            from django.db import models


            class Widget(models.Model):
                name = models.CharField(max_length=100)
            """
        )
    )
    (project_dir / "test_consumer.py").write_text(
        textwrap.dedent(
            """
            from consumer_app.models import Widget


            def test_db_fixture_works(db):
                Widget.objects.create(name="a")
                assert Widget.objects.count() == 1
            """
        )
    )


def test_fixture_module_configures_django_end_to_end(tmp_path: Path) -> None:
    _write_consumer_project(tmp_path)

    result = run_rustest(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stderr


def test_unresolved_settings_still_runs_non_django_tests(tmp_path: Path) -> None:
    (tmp_path / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (tmp_path / "test_plain.py").write_text(
        "def test_plain_math():\n    assert 1 + 1 == 2\n"
    )

    result = run_rustest(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stderr


def test_invalid_config_fails_every_test(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [tool.rustest-django]
            not_a_real_key = true
            """
        )
    )
    (tmp_path / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (tmp_path / "test_plain.py").write_text(
        "def test_plain_math():\n    assert 1 + 1 == 2\n"
    )

    result = run_rustest(tmp_path)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "1 failed" in result.stderr
    assert "not_a_real_key" in result.stderr
