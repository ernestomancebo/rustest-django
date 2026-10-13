from pathlib import Path

from _helpers import run_rustest
from rustest import fixture, parametrize


@fixture
def config_project(tmp_path: Path, monkeypatch) -> Path:
    for name in (
        "DJANGO_SETTINGS_MODULE",
        "DJANGO_CONFIGURATION",
        "FAIL_INVALID_TEMPLATE_VARS",
        "DJANGO_LIVE_TEST_SERVER_ADDRESS",
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


@parametrize("value", ["-1", "65536", "true", "1.5", '"8000"'])
def test_live_server_port_rejects_invalid_native_values(
    config_project: Path, value: str
) -> None:
    (config_project / "pyproject.toml").write_text(
        f"[tool.rustest-django]\nlive_server_port = {value}\n"
    )
    (config_project / "test_consumer.py").write_text("def test_runs():\n    pass\n")

    result = run_rustest(config_project)

    assert result.returncode != 0
    assert "must be an integer between 0 and 65535" in result.stdout + result.stderr


@parametrize("key", ["settings_module", "configuration", "live_server_host"])
@parametrize("value", ["123", '"  "'])
def test_string_settings_reject_non_strings_and_empty_values(
    config_project: Path, key: str, value: str
) -> None:
    (config_project / "pyproject.toml").write_text(
        f"[tool.rustest-django]\n{key} = {value}\n"
    )
    (config_project / "test_consumer.py").write_text("def test_runs():\n    pass\n")

    result = run_rustest(config_project)

    assert result.returncode != 0
    assert f"{key}=" in result.stdout + result.stderr
    assert "must be a non-empty string" in result.stdout + result.stderr


@parametrize("source", ["native", "env", "pytest.ini", "pytest-toml"])
def test_configuration_class_is_selected_before_django_setup(
    config_project: Path, monkeypatch, source: str
) -> None:
    (config_project / "consumer_settings.py").write_text(
        "from configurations import Configuration\n"
        "class Consumer(Configuration):\n"
        '    SECRET_KEY = "consumer-secret"\n'
        "    INSTALLED_APPS = []\n    DEBUG = True\n"
    )
    if source == "native":
        (config_project / "pyproject.toml").write_text(
            '[tool.rustest-django]\nsettings_module = "consumer_settings"\n'
            'configuration = "Consumer"\ndebug_mode = "keep"\n'
        )
    elif source == "env":
        monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "consumer_settings")
        monkeypatch.setenv("DJANGO_CONFIGURATION", "Consumer")
        monkeypatch.setenv("RUSTEST_DJANGO_DEBUG_MODE", "keep")
    elif source == "pytest.ini":
        (config_project / "pytest.ini").write_text(
            "[pytest]\nDJANGO_SETTINGS_MODULE = consumer_settings\n"
            "DJANGO_CONFIGURATION = Consumer\ndjango_debug_mode = keep\n"
        )
    else:
        (config_project / "pyproject.toml").write_text(
            '[tool.pytest]\nDJANGO_SETTINGS_MODULE = "consumer_settings"\n'
            'DJANGO_CONFIGURATION = "Consumer"\ndjango_debug_mode = "keep"\n'
        )

    result = run_rustest(config_project)

    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_optional_configuration_dependency_explains_installation(
    config_project: Path, monkeypatch
) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "consumer_settings")
    monkeypatch.setenv("DJANGO_CONFIGURATION", "Consumer")
    (config_project / "conftest.py").write_text(
        "import sys\nfrom importlib.abc import MetaPathFinder\n"
        "class UnavailableOptionalDependency(MetaPathFinder):\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        '        if fullname == "configurations":\n'
        '            raise ModuleNotFoundError("No configurations", '
        'name="configurations")\n'
        "sys.meta_path.insert(0, UnavailableOptionalDependency())\n"
        'rustest_fixtures = ["rustest_django"]\n'
    )
    (config_project / "test_consumer.py").write_text("def test_runs():\n    pass\n")

    result = run_rustest(config_project)

    assert result.returncode != 0
    assert "Install django-configurations" in result.stdout + result.stderr


@parametrize("key", ["django_find_project", "FAIL_INVALID_TEMPLATE_VARS"])
@parametrize("source", ["pytest.ini", ".pytest.ini", "pytest-toml"])
def test_invalid_fallback_booleans_fail_with_the_setting_name(
    config_project: Path, key: str, source: str
) -> None:
    if source == "pytest-toml":
        (config_project / "pyproject.toml").write_text(
            f'[tool.pytest.ini_options]\n{key} = "banana"\n'
        )
    else:
        (config_project / source).write_text(f"[pytest]\n{key} = banana\n")
    (config_project / "test_consumer.py").write_text("def test_runs():\n    pass\n")

    result = run_rustest(config_project)

    assert result.returncode != 0
    assert f"{key}=" in result.stdout + result.stderr
    assert "is not a valid boolean" in result.stdout + result.stderr


def test_upstream_template_environment_boolean_is_validated(
    config_project: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FAIL_INVALID_TEMPLATE_VARS", "banana")
    (config_project / "test_consumer.py").write_text("def test_runs():\n    pass\n")

    result = run_rustest(config_project)

    assert result.returncode != 0
    assert "FAIL_INVALID_TEMPLATE_VARS=" in result.stdout + result.stderr
    assert "is not a valid boolean" in result.stdout + result.stderr


@parametrize("address", ["localhost:8000-8002", "localhost:8000,8002", ":8000"])
def test_live_server_address_rejects_unsupported_forms(
    config_project: Path, monkeypatch, address: str
) -> None:
    monkeypatch.setenv("DJANGO_LIVE_TEST_SERVER_ADDRESS", address)
    (config_project / "test_consumer.py").write_text("def test_runs():\n    pass\n")

    result = run_rustest(config_project)

    assert result.returncode != 0
    assert "DJANGO_LIVE_TEST_SERVER_ADDRESS=" in result.stdout + result.stderr
    assert "Use host or host:port" in result.stdout + result.stderr


@parametrize("source", ["pytest.ini", "pyproject.toml"])
def test_empty_nearest_configuration_stops_parent_discovery(
    config_project: Path,
    source: str,
) -> None:
    (config_project / "pyproject.toml").write_text(
        '[tool.rustest-django]\ndebug_mode = "keep"\n'
    )
    (config_project / "conftest.py").unlink()
    child = config_project / "consumer"
    child.mkdir()
    (child / source).write_text(
        "[tool.rustest-django]\n" if source == "pyproject.toml" else ""
    )
    (child / "conftest.py").write_text(
        "from django.conf import settings\n"
        'settings.configure(SECRET_KEY="consumer-secret", DEBUG=True)\n'
        'rustest_fixtures = ["rustest_django"]\n'
    )
    (child / "test_consumer.py").write_text(
        "from django.conf import settings\n"
        "def test_defaults():\n    assert settings.DEBUG is False\n"
    )

    result = run_rustest(child)

    assert result.returncode == 0, result.stdout + result.stderr


@parametrize(
    "toml,section",
    [
        ('tool = "invalid"\n', "tool"),
        ('[tool]\nrustest-django = "invalid"\n', "tool.rustest-django"),
        ('[tool]\npytest = "invalid"\n', "tool.pytest"),
        ('[tool.pytest]\nini_options = "invalid"\n', "tool.pytest.ini_options"),
    ],
)
def test_configuration_sections_must_be_tables(
    config_project: Path, toml: str, section: str
) -> None:
    (config_project / "pyproject.toml").write_text(toml)
    (config_project / "conftest.py").unlink()
    child = config_project / "consumer"
    child.mkdir()
    (child / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (child / "test_consumer.py").write_text("def test_runs():\n    pass\n")

    result = run_rustest(child)

    assert result.returncode != 0
    assert f"{section} must be a TOML table" in result.stdout + result.stderr, (
        result.stdout + result.stderr
    )
