from pathlib import Path

from _helpers import run_rustest
from rustest import fixture, parametrize


@fixture
def config_project(tmp_path: Path, monkeypatch) -> Path:
    for name in (
        "DJANGO_SETTINGS_MODULE",
        "DJANGO_CONFIGURATION",
        "FAIL_INVALID_TEMPLATE_VARS",
        "RUSTEST_DJANGO_REUSE_DB",
        "RUSTEST_DJANGO_CREATE_DB",
        "RUSTEST_DJANGO_MIGRATIONS",
        "RUSTEST_DJANGO_FIND_PROJECT",
        "RUSTEST_DJANGO_DEBUG_MODE",
        "RUSTEST_DJANGO_LIVE_SERVER_HOST",
        "RUSTEST_DJANGO_LIVE_SERVER_PORT",
        "RUSTEST_DJANGO_FAIL_ON_TEMPLATE_VARS",
    ):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (tmp_path / "consumer_settings.py").write_text(
        'SECRET_KEY = "consumer-secret"\nINSTALLED_APPS = []\nDEBUG = True\n'
    )
    (tmp_path / "test_consumer.py").write_text(
        "from django.conf import settings\n"
        "def test_settings():\n"
        '    assert settings.SECRET_KEY == "consumer-secret"\n'
        "    assert settings.DEBUG is True\n"
    )
    return tmp_path


def test_pytest_ini_configures_django_before_test_import(config_project: Path) -> None:
    (config_project / "pytest.ini").write_text(
        "[pytest]\nDJANGO_SETTINGS_MODULE = consumer_settings\n"
        "django_debug_mode = keep\ndjango_find_project = false\n"
    )

    result = run_rustest(config_project)

    assert result.returncode == 0, result.stdout + result.stderr


def test_native_configuration_overrides_ini_fallback(config_project: Path) -> None:
    (config_project / "pytest.ini").write_text(
        "[pytest]\nDJANGO_SETTINGS_MODULE = nonexistent_settings\n"
        "django_debug_mode = false\n"
    )
    (config_project / "pyproject.toml").write_text(
        '[tool.rustest-django]\nsettings_module = "consumer_settings"\n'
        'debug_mode = "keep"\n'
    )

    result = run_rustest(config_project)

    assert result.returncode == 0, result.stdout + result.stderr


def test_pytest_native_toml_configures_django(config_project: Path) -> None:
    (config_project / "pyproject.toml").write_text(
        '[tool.pytest]\nDJANGO_SETTINGS_MODULE = "consumer_settings"\n'
        'django_debug_mode = "keep"\ndjango_find_project = false\n'
    )

    result = run_rustest(config_project)

    assert result.returncode == 0, result.stdout + result.stderr


@parametrize("key", ["reuse_db", "migrations", "find_project", "fail_on_template_vars"])
@parametrize("value", ['"false"', "0"])
def test_native_boolean_settings_reject_non_booleans(
    config_project: Path, key: str, value: str
) -> None:
    (config_project / "pyproject.toml").write_text(
        f"[tool.rustest-django]\n{key} = {value}\n"
    )
    (config_project / "test_consumer.py").write_text("def test_runs():\n    pass\n")

    result = run_rustest(config_project)

    assert result.returncode != 0
    assert f"{key}=" in result.stdout + result.stderr
    assert "must be a TOML boolean" in result.stdout + result.stderr
