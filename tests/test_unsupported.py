import os
import subprocess
import sys
import textwrap
from pathlib import Path

from rustest import FixtureRequest, fixture


@fixture
def _live_server_error(request: FixtureRequest):
    try:
        request.getfixturevalue("live_server")
    except RuntimeError as exc:
        return exc
    return None


@fixture
def _django_db_serialized_rollback_error(request: FixtureRequest):
    try:
        request.getfixturevalue("django_db_serialized_rollback")
    except RuntimeError as exc:
        return exc
    return None


@fixture
def _django_isolated_apps_error(request: FixtureRequest):
    try:
        request.getfixturevalue("django_isolated_apps")
    except RuntimeError as exc:
        return exc
    return None


def test_live_server_is_unsupported(_live_server_error) -> None:
    assert _live_server_error is not None
    message = str(_live_server_error)
    assert message.startswith("rustest-django: ")
    assert "live_server" in message
    assert "unsupported in rustest-django v1" in message


def test_django_db_serialized_rollback_fixture_is_unsupported(
    _django_db_serialized_rollback_error,
) -> None:
    assert _django_db_serialized_rollback_error is not None
    message = str(_django_db_serialized_rollback_error)
    assert message.startswith("rustest-django: ")
    assert "django_db_serialized_rollback" in message
    assert "try db instead" in message


def test_django_isolated_apps_is_unsupported(_django_isolated_apps_error) -> None:
    assert _django_isolated_apps_error is not None
    message = str(_django_isolated_apps_error)
    assert message.startswith("rustest-django: ")
    assert "django_isolated_apps" in message


def _run_rustest(project_dir: Path) -> subprocess.CompletedProcess:
    # A wide COLUMNS keeps rustest's own output renderer from hard-wrapping
    # long error messages mid-word, which would break substring assertions.
    return subprocess.run(
        [sys.executable, "-m", "rustest", "--color=never", str(project_dir)],
        cwd=project_dir,
        capture_output=True,
        text=True,
        env={**os.environ, "COLUMNS": "300"},
    )


def test_urls_marker_is_unsupported(tmp_path: Path) -> None:
    (tmp_path / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (tmp_path / "test_consumer.py").write_text(
        textwrap.dedent(
            """
            from rustest import mark


            @mark.urls("some.urls.module")
            def test_uses_urls_marker():
                assert True
            """
        )
    )

    result = _run_rustest(tmp_path)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "1 failed" in result.stderr
    assert "rustest-django: " in result.stderr
    assert "unsupported in rustest-django v1" in result.stderr
    assert "Override settings.ROOT_URLCONF via the settings fixture" in result.stderr


def test_ignore_template_errors_marker_is_unsupported(tmp_path: Path) -> None:
    (tmp_path / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (tmp_path / "test_consumer.py").write_text(
        textwrap.dedent(
            """
            from rustest import mark


            @mark.ignore_template_errors
            def test_uses_ignore_template_errors_marker():
                assert True
            """
        )
    )

    result = _run_rustest(tmp_path)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "1 failed" in result.stderr
    assert "rustest-django: " in result.stderr
    assert "unsupported in rustest-django v1" in result.stderr
