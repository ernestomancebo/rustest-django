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
    assert "live_server" in str(_live_server_error)
    assert "unsupported in rustest-django v1" in str(_live_server_error)


def test_django_db_serialized_rollback_fixture_is_unsupported(
    _django_db_serialized_rollback_error,
) -> None:
    assert _django_db_serialized_rollback_error is not None
    assert "django_db_serialized_rollback" in str(_django_db_serialized_rollback_error)


def test_django_isolated_apps_is_unsupported(_django_isolated_apps_error) -> None:
    assert _django_isolated_apps_error is not None
    assert "django_isolated_apps" in str(_django_isolated_apps_error)


def _run_rustest(project_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "rustest", "--color=never", str(project_dir)],
        cwd=project_dir,
        capture_output=True,
        text=True,
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
    assert "unsupported in rustest-django v1" in result.stderr
