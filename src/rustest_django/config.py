from __future__ import annotations

import os
import sys
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
}

_DEBUG_MODE_VALUES = ("true", "false", "keep")


@dataclass(frozen=True)
class ResolvedConfig:
    settings_module: str | None
    reuse_db: bool
    create_db: bool
    migrations: bool
    find_project: bool
    debug_mode: str


def resolve_config(start_dir: Path) -> ResolvedConfig:
    project, ini = _load_pyproject_sections(start_dir)

    create_db = _env_bool("RUSTEST_DJANGO_CREATE_DB", project, None, default=False)
    reuse_db = create_db is False and _env_bool(
        "RUSTEST_DJANGO_REUSE_DB", project, "reuse_db", default=False
    )

    return ResolvedConfig(
        settings_module=os.environ.get("DJANGO_SETTINGS_MODULE")
        or project.get("settings_module")
        or ini.get("DJANGO_SETTINGS_MODULE"),
        reuse_db=reuse_db,
        create_db=create_db,
        migrations=_env_bool(
            "RUSTEST_DJANGO_MIGRATIONS", project, "migrations", default=True
        ),
        find_project=_env_bool(
            "RUSTEST_DJANGO_FIND_PROJECT",
            project,
            "find_project",
            default=ini.get("django_find_project", True),
        ),
        debug_mode=_debug_mode(project, ini),
    )


def _load_pyproject_sections(start_dir: Path) -> tuple[dict, dict]:
    for directory in (start_dir, *start_dir.parents):
        pyproject = directory / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            data = tomllib.loads(pyproject.read_text())
        except tomllib.TOMLDecodeError as error:
            raise ConfigError(
                _message(f"{pyproject} is not valid TOML: {error}")
            ) from error
        tool = data.get("tool", {})
        project = tool.get("rustest-django", {})
        ini = tool.get("pytest", {}).get("ini_options", {})
        if project or ini:
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
    env_name: str, project: dict, project_key: str | None, *, default: bool
) -> bool:
    raw = os.environ.get(env_name)
    if raw is not None:
        normalized = raw.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off"):
            return False
        raise ConfigError(
            _message(
                f"{env_name}={raw!r} is not a valid boolean. Use one of: "
                "1/true/yes/on or 0/false/no/off."
            )
        )
    if project_key is not None and project_key in project:
        return bool(project[project_key])
    return default


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
