import os
import subprocess
import sys
import time
from pathlib import Path

CONFTEST = """
import sys
import types

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

for index in range(%(modules)d):
    module = types.ModuleType(f"synthetic_{index}")
    module.__file__ = f"/nonexistent/synthetic/package_{index}/module.py"
    for attribute in range(100):
        setattr(module, f"attribute_{attribute}", attribute)
    sys.modules[module.__name__] = module
"""

TESTS = """
from rustest import fixture

@fixture(autouse=True)
def _consumer_autouse():
    return 1

""" + "".join(
    f"def test_plain_{index}(db):\n    assert True\n\n" for index in range(100)
)


def _timed_run(project: Path, modules: int, tests: str = TESTS) -> float:
    (project / "conftest.py").write_text(CONFTEST % {"modules": modules})
    (project / "test_consumer.py").write_text(tests)
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "rustest", "--color=never", str(project)],
        cwd=project,
        capture_output=True,
        text=True,
        env={**os.environ, "COLUMNS": "300"},
    )
    elapsed = time.perf_counter() - started
    assert result.returncode == 0, result.stdout + result.stderr
    return elapsed


def test_per_test_cost_does_not_grow_with_loaded_modules(tmp_path: Path) -> None:
    small = tmp_path / "small"
    large = tmp_path / "large"
    small.mkdir()
    large.mkdir()
    baseline = min(_timed_run(small, 10), _timed_run(small, 10))
    crowded = _timed_run(large, 5000)
    # Both runs execute the same 100 tests; only the number of loaded modules
    # differs. Setup of the crowded run costs a little, so allow a margin.
    assert crowded < baseline * 1.6 + 1.0, (baseline, crowded)


CLASS_TESTS = (
    "from rustest_django import django_db\n\n"
    "@django_db\nclass TestMany:\n"
    + "".join(
        f"    def test_method_{index}(self):\n        assert True\n"
        for index in range(100)
    )
)


def test_class_based_per_test_cost_does_not_grow_with_loaded_modules(
    tmp_path: Path,
) -> None:
    small = tmp_path / "small"
    large = tmp_path / "large"
    small.mkdir()
    large.mkdir()
    baseline = min(
        _timed_run(small, 10, CLASS_TESTS), _timed_run(small, 10, CLASS_TESTS)
    )
    crowded = _timed_run(large, 5000, CLASS_TESTS)
    assert crowded < baseline * 1.6 + 1.0, (baseline, crowded)
