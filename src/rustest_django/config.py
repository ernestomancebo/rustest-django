from __future__ import annotations

import os
import sys
from configparser import ConfigParser
from configparser import Error as IniError
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # ty: ignore[unresolved-import]

from rustest_django._errors import ConfigError, _message

_KNOWN_TOOL_KEYS = {
    "settings_module",
    "reuse_db",
    "migrations",
    "find_project",
    "debug_mode",
    "fail_on_template_vars",
    "live_server_port",
    "live_server_host",
    "configuration",
}

_DEBUG_MODE_VALUES = ("true", "false", "keep")


class _CaseSensitiveConfigParser(ConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr


@dataclass(frozen=True)
class ResolvedConfig:
    settings_module: str | None
    reuse_db: bool
    create_db: bool
    migrations: bool
    find_project: bool
    debug_mode: str
    fail_on_template_vars: bool = False
    live_server_port: int = 0
    live_server_host: str = "localhost"
    configuration: str | None = None


def resolve_config(start_dir: Path) -> ResolvedConfig:
    project, ini = _load_pyproject_sections(start_dir)
    address_host, address_port = "localhost", 0
    if not (
        (
            "RUSTEST_DJANGO_LIVE_SERVER_HOST" in os.environ
            or "live_server_host" in project
        )
        and (
            "RUSTEST_DJANGO_LIVE_SERVER_PORT" in os.environ
            or "live_server_port" in project
        )
    ):
        address_host, address_port = _live_server_address()

    create_db = _env_bool("RUSTEST_DJANGO_CREATE_DB", project, None, default=False)
    reuse_db = create_db is False and _env_bool(
        "RUSTEST_DJANGO_REUSE_DB", project, "reuse_db", default=False
    )

    return ResolvedConfig(
        settings_module=_string(
            "DJANGO_SETTINGS_MODULE", project, "settings_module", ini
        ),
        reuse_db=reuse_db,
        create_db=create_db,
        migrations=_env_bool(
            "RUSTEST_DJANGO_MIGRATIONS", project, "migrations", default=True
        ),
        find_project=_env_bool(
            "RUSTEST_DJANGO_FIND_PROJECT",
            project,
            "find_project",
            default=True,
            ini=ini,
            ini_key="django_find_project",
        ),
        debug_mode=_debug_mode(project, ini),
        fail_on_template_vars=_env_bool(
            "RUSTEST_DJANGO_FAIL_ON_TEMPLATE_VARS",
            project,
            "fail_on_template_vars",
            default=False,
            ini=ini,
            ini_key="FAIL_INVALID_TEMPLATE_VARS",
            env_aliases=("FAIL_INVALID_TEMPLATE_VARS",),
        ),
        live_server_port=_live_server_port(project, default=address_port),
        live_server_host=_string(
            "RUSTEST_DJANGO_LIVE_SERVER_HOST",
            project,
            "live_server_host",
            {},
            default=address_host,
        )
        or "localhost",
        configuration=_string("DJANGO_CONFIGURATION", project, "configuration", ini),
    )


def _load_pyproject_sections(start_dir: Path) -> tuple[dict, dict]:
    """Use the nearest directory with native/pytest TOML or an INI file.

    In that directory native TOML defaults coexist with one pytest fallback:
    pytest.ini, .pytest.ini, then native pytest TOML, then ini_options. An empty
    INI file or supported TOML table stops the upward search even when empty;
    unrelated pyproject files do not.
    """
    for directory in (start_dir, *start_dir.parents):
        project, ini = {}, {}
        ini_found = False
        toml_found = False
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            try:
                data = tomllib.loads(pyproject.read_text())
            except tomllib.TOMLDecodeError as error:
                raise ConfigError(
                    _message(f"{pyproject} is not valid TOML: {error}")
                ) from error
            tool = data.get("tool", {})
            if not isinstance(tool, dict):
                raise ConfigError(_message("tool must be a TOML table."))
            toml_found = "rustest-django" in tool or "pytest" in tool
            project = tool.get("rustest-django", {})
            pytest = tool.get("pytest", {})
            for section, value in (
                ("tool.rustest-django", project),
                ("tool.pytest", pytest),
            ):
                if not isinstance(value, dict):
                    raise ConfigError(_message(f"{section} must be a TOML table."))
            ini = {key: value for key, value in pytest.items() if key != "ini_options"}
            if not ini:
                ini = pytest.get("ini_options", {})
                if not isinstance(ini, dict):
                    raise ConfigError(
                        _message("tool.pytest.ini_options must be a TOML table.")
                    )
        for name in ("pytest.ini", ".pytest.ini"):
            ini_file = directory / name
            if not ini_file.is_file():
                continue
            ini_found = True
            parser = _CaseSensitiveConfigParser(interpolation=None)
            try:
                parser.read_string(ini_file.read_text())
                ini: dict = (
                    dict(parser["pytest"]) if parser.has_section("pytest") else {}
                )
            except (IniError, ValueError) as error:
                raise ConfigError(
                    _message(f"{ini_file} is not valid INI: {error}")
                ) from error
            break
        if toml_found or ini_found:
            unknown = set(project) - _KNOWN_TOOL_KEYS
            if unknown:
                raise ConfigError(
                    _message(
                        "Unknown key(s) in [tool.rustest-django]: "
                        f"{', '.join(sorted(unknown))}. Valid keys: "
                        f"{', '.join(sorted(_KNOWN_TOOL_KEYS))}."
                    )
                )
            return project, ini
    return {}, {}


def _env_bool(
    env_name: str,
    project: dict,
    project_key: str | None,
    *,
    default: bool,
    ini: dict | None = None,
    ini_key: str | None = None,
    env_aliases: tuple[str, ...] = (),
) -> bool:
    for name in (env_name, *env_aliases):
        raw = os.environ.get(name)
        if raw is not None:
            return _parse_bool(name, raw)
    if project_key is not None and project_key in project:
        value = project[project_key]
        if not isinstance(value, bool):
            raise ConfigError(
                _message(
                    f"{project_key}={value!r} must be a TOML boolean (true or false)."
                )
            )
        return value
    if ini is not None and ini_key is not None and ini_key in ini:
        return _parse_bool(ini_key, ini[ini_key])
    return default


def _parse_bool(name: str, value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off"):
            return False
    raise ConfigError(
        _message(
            f"{name}={value!r} is not a valid boolean. Use one of: "
            "1/true/yes/on or 0/false/no/off."
        )
    )


def _debug_mode(project: dict, ini: dict) -> str:
    if "RUSTEST_DJANGO_DEBUG_MODE" in os.environ:
        raw: object = os.environ["RUSTEST_DJANGO_DEBUG_MODE"]
    elif "debug_mode" in project:
        raw = project["debug_mode"]
    elif "django_debug_mode" in ini:
        raw = ini["django_debug_mode"]
    else:
        return "false"

    if isinstance(raw, str) and raw.strip().lower() in _DEBUG_MODE_VALUES:
        return raw.strip().lower()

    raise ConfigError(
        _message(
            f"debug_mode={raw!r} is not a valid debug_mode. Use one of: "
            f"{', '.join(_DEBUG_MODE_VALUES)}."
        )
    )


def _live_server_port(project: dict, *, default: int = 0) -> int:
    raw = os.environ.get("RUSTEST_DJANGO_LIVE_SERVER_PORT")
    if raw is not None:
        try:
            value = int(raw)
        except ValueError:
            value = None
    else:
        value = project.get("live_server_port", default)
    if type(value) is not int or not 0 <= value <= 65535:
        raise ConfigError(
            _message(
                f"live_server_port={raw if raw is not None else value!r} "
                "must be an integer between 0 and 65535."
            )
        )
    return value


def _live_server_address() -> tuple[str, int]:
    raw = os.environ.get("DJANGO_LIVE_TEST_SERVER_ADDRESS")
    if raw is None:
        return "localhost", 0
    address = raw.strip()
    host, separator, port = address.partition(":")
    if host and not any(character.isspace() for character in host):
        if not separator:
            return host, 0
        if port.isdecimal() and 0 <= int(port) <= 65535:
            return host, int(port)
    raise ConfigError(
        _message(
            f"DJANGO_LIVE_TEST_SERVER_ADDRESS={raw!r} is not a supported address. "
            "Use host or host:port (0 to 65535); port lists and ranges are unsupported."
        )
    )


def _string(
    env_name: str,
    project: dict,
    key: str,
    ini: dict,
    *,
    default: str | None = None,
) -> str | None:
    if env_name in os.environ:
        value = os.environ[env_name]
    elif key in project:
        value = project[key]
    elif env_name in ini:
        value = ini[env_name]
    else:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(_message(f"{key}={value!r} must be a non-empty string."))
    return value.strip()
