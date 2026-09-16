from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # ty: ignore[unresolved-import]


class ConfigError(Exception):
    pass


_KNOWN_TOOL_KEYS = {
    "settings_module",
    "reuse_db",
    "migrations",
    "find_project",
    "debug_mode",
}


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
        debug_mode=os.environ.get("RUSTEST_DJANGO_DEBUG_MODE")
        or project.get("debug_mode")
        or ini.get("django_debug_mode", "false"),
    )


def _load_pyproject_sections(start_dir: Path) -> tuple[dict, dict]:
    for directory in (start_dir, *start_dir.parents):
        pyproject = directory / "pyproject.toml"
        if not pyproject.is_file():
            continue
        data = tomllib.loads(pyproject.read_text())
        tool = data.get("tool", {})
        project = tool.get("rustest-django", {})
        ini = tool.get("pytest", {}).get("ini_options", {})
        if project or ini:
            unknown = set(project) - _KNOWN_TOOL_KEYS
            if unknown:
                raise ConfigError(
                    "Unknown key(s) in [tool.rustest-django]: "
                    f"{', '.join(sorted(unknown))}"
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
        raise ConfigError(f"{env_name}={raw!r} is not a valid boolean")
    if project_key is not None and project_key in project:
        return bool(project[project_key])
    return default
