"""Runs Django setup at fixture-module import time, per docs/spec/configuration.md
'When Django is set up': the only point early enough to run before test modules
import models.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

import django
import django.conf
from rustest import fixture

from rustest_django.config import ResolvedConfig, resolve_config

error: Exception | None = None
resolved_config: ResolvedConfig | None = None


def _find_start_dir() -> Path:
    for module in list(sys.modules.values()):
        file = getattr(module, "__file__", None)
        if file and Path(file).name == "conftest.py":
            return Path(file).resolve().parent
    if sys.path and sys.path[0]:
        return Path(sys.path[0])
    return Path.cwd()


def _find_project_dir(start_dir: Path) -> Path | None:
    for directory in (start_dir, *start_dir.parents):
        if (directory / "manage.py").is_file():
            return directory
    return None


def run() -> None:
    global error, resolved_config
    try:
        start_dir = _find_start_dir()
        config = resolve_config(start_dir)
        resolved_config = config

        if config.find_project:
            project_dir = _find_project_dir(start_dir)
            if project_dir is not None and str(project_dir) not in sys.path:
                sys.path.insert(0, str(project_dir))

        if config.settings_module:
            os.environ["DJANGO_SETTINGS_MODULE"] = config.settings_module

        settings_ready = os.environ.get("DJANGO_SETTINGS_MODULE")
        if settings_ready and not django.conf.settings.configured:
            django.setup()
    except Exception as exc:  # noqa: BLE001
        error = exc
        traceback.print_exc(file=sys.stderr)


@fixture(autouse=True, scope="session")
def _rustest_django_bootstrap_check():
    if error is not None:
        raise RuntimeError(
            f"rustest-django failed to configure Django at import time: {error}"
        ) from error
    yield


run()
