import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

from rustest.fixture_registry import _fixture_registry, register_fixtures


def run_rustest(project_dir: Path) -> subprocess.CompletedProcess:
    # A wide COLUMNS keeps rustest's own output renderer from hard-wrapping
    # long error messages mid-word, which would break substring assertions.
    return subprocess.run(
        [sys.executable, "-m", "rustest", "--color=never", str(project_dir)],
        cwd=project_dir,
        capture_output=True,
        text=True,
        env={**os.environ, "COLUMNS": "300"},
    )


DJANGO_CONFTEST = """
import django
from django.conf import settings

settings.configure(
    SECRET_KEY="test-secret",
    INSTALLED_APPS=["django.contrib.contenttypes"],
    DATABASES={"default": {
        "ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:",
    }},
)
django.setup()
rustest_fixtures = ["rustest_django"]
"""


def write_django_conftest(directory: Path, extra: str = "") -> None:
    """Write a consumer conftest that configures Django and loads the plugin."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "conftest.py").write_text(DJANGO_CONFTEST + extra)


@contextmanager
def temporary_module(
    module: ModuleType, fixtures: dict[str, object] | None = None
) -> Iterator[None]:
    """Put a module in sys.modules, and optionally fixtures in the registry."""
    saved = dict(_fixture_registry)
    sys.modules[module.__name__] = module
    if fixtures:
        register_fixtures({**saved, **fixtures})
    try:
        yield
    finally:
        del sys.modules[module.__name__]
        register_fixtures(saved)
