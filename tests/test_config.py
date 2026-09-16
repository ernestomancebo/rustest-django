from pathlib import Path

from rustest import parametrize, raises

from rustest_django.config import ConfigError, resolve_config


def test_defaults_with_no_config_source(tmp_path: Path, monkeypatch) -> None:
    for key in (
        "DJANGO_SETTINGS_MODULE",
        "RUSTEST_DJANGO_REUSE_DB",
        "RUSTEST_DJANGO_CREATE_DB",
        "RUSTEST_DJANGO_MIGRATIONS",
        "RUSTEST_DJANGO_FIND_PROJECT",
        "RUSTEST_DJANGO_DEBUG_MODE",
    ):
        monkeypatch.delenv(key, raising=False)

    config = resolve_config(tmp_path)

    assert config.settings_module is None
    assert config.reuse_db is False
    assert config.create_db is False
    assert config.migrations is True
    assert config.find_project is True
    assert config.debug_mode == "false"


@parametrize(
    "env_var,attr",
    [
        ("RUSTEST_DJANGO_REUSE_DB", "reuse_db"),
        ("RUSTEST_DJANGO_CREATE_DB", "create_db"),
        ("RUSTEST_DJANGO_FIND_PROJECT", "find_project"),
    ],
)
def test_env_var_true_sets_bool_key(
    tmp_path: Path, monkeypatch, env_var: str, attr: str
) -> None:
    monkeypatch.setenv(env_var, "true")

    config = resolve_config(tmp_path)

    assert getattr(config, attr) is True


def test_env_var_false_clears_migrations_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RUSTEST_DJANGO_MIGRATIONS", "false")

    config = resolve_config(tmp_path)

    assert config.migrations is False


def test_env_var_sets_settings_module(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "myproject.settings")

    config = resolve_config(tmp_path)

    assert config.settings_module == "myproject.settings"


def test_env_var_sets_debug_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RUSTEST_DJANGO_DEBUG_MODE", "keep")

    config = resolve_config(tmp_path)

    assert config.debug_mode == "keep"


def test_pyproject_tool_section_sets_defaults(tmp_path: Path, monkeypatch) -> None:
    for key in ("DJANGO_SETTINGS_MODULE", "RUSTEST_DJANGO_REUSE_DB"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / "pyproject.toml").write_text(
        """
        [tool.rustest-django]
        settings_module = "myproject.settings"
        reuse_db = true
        """
    )

    config = resolve_config(tmp_path)

    assert config.settings_module == "myproject.settings"
    assert config.reuse_db is True


def test_env_var_overrides_pyproject_tool_section(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "from_env.settings")
    (tmp_path / "pyproject.toml").write_text(
        """
        [tool.rustest-django]
        settings_module = "from_pyproject.settings"
        """
    )

    config = resolve_config(tmp_path)

    assert config.settings_module == "from_env.settings"


def test_pytest_ini_options_fallback_when_tool_section_absent(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    (tmp_path / "pyproject.toml").write_text(
        """
        [tool.pytest.ini_options]
        DJANGO_SETTINGS_MODULE = "ini.settings"
        django_find_project = false
        django_debug_mode = "keep"
        """
    )

    config = resolve_config(tmp_path)

    assert config.settings_module == "ini.settings"
    assert config.find_project is False
    assert config.debug_mode == "keep"


def test_walks_up_to_find_pyproject_toml(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    (tmp_path / "pyproject.toml").write_text(
        """
        [tool.rustest-django]
        settings_module = "parent.settings"
        """
    )
    start_dir = tmp_path / "conftest_dir"
    start_dir.mkdir()

    config = resolve_config(start_dir)

    assert config.settings_module == "parent.settings"


def test_skips_pyproject_with_neither_section(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    (tmp_path / "pyproject.toml").write_text(
        """
        [tool.rustest-django]
        settings_module = "grandparent.settings"
        """
    )
    start_dir = tmp_path / "unrelated_pkg" / "conftest_dir"
    start_dir.mkdir(parents=True)
    (tmp_path / "unrelated_pkg" / "pyproject.toml").write_text(
        """
        [project]
        name = "unrelated"
        """
    )

    config = resolve_config(start_dir)

    assert config.settings_module == "grandparent.settings"


def test_unparsable_env_bool_fails_fast(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RUSTEST_DJANGO_REUSE_DB", "banana")

    with raises(ConfigError):
        resolve_config(tmp_path)


def test_unknown_key_in_tool_section_fails_fast(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
        [tool.rustest-django]
        not_a_real_key = true
        """
    )

    with raises(ConfigError):
        resolve_config(tmp_path)


def test_create_db_cancels_reuse_db(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RUSTEST_DJANGO_CREATE_DB", "true")
    monkeypatch.setenv("RUSTEST_DJANGO_REUSE_DB", "true")

    config = resolve_config(tmp_path)

    assert config.create_db is True
    assert config.reuse_db is False
