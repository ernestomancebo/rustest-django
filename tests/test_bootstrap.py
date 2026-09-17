import textwrap
from pathlib import Path

from _helpers import run_rustest


def test_django_setup_failure_reports_once(tmp_path: Path) -> None:
    badapp = tmp_path / "badapp"
    badapp.mkdir()
    (badapp / "__init__.py").write_text('raise ImportError("BOOTSTRAP_TEST_MARKER")\n')
    (tmp_path / "settings.py").write_text(
        textwrap.dedent(
            """
            INSTALLED_APPS = ["badapp"]
            DATABASES = {
                "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
            }
            USE_TZ = True
            """
        )
    )
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [tool.rustest-django]
            settings_module = "settings"
            """
        )
    )
    (tmp_path / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (tmp_path / "test_consumer.py").write_text("def test_plain():\n    assert True\n")

    result = run_rustest(tmp_path)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "1 failed" in result.stderr
    assert "rustest-django: failed to configure Django at import time" in result.stderr
    # The original ImportError's traceback is preserved via exception chaining
    # (`raise ... from error`), which Python renders as two "Traceback" blocks
    # joined by "The above exception was the direct cause of...". A leftover
    # manual traceback.print_exc() would print the original exception's
    # traceback a second time, on its own, before this chained report.
    assert result.stderr.count("Traceback (most recent call last):") == 2
