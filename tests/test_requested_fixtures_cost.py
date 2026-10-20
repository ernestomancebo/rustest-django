import time
from pathlib import Path

from _helpers import run_rustest, write_django_conftest
from rustest import parametrize

SYNTHETIC_MODULES = """
import sys
import types

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


CLASS_TESTS = (
    "from rustest_django import django_db\n\n"
    "@django_db\nclass TestMany:\n"
    + "".join(
        f"    def test_method_{index}(self):\n        assert True\n"
        for index in range(100)
    )
)


def _timed_run(project: Path, modules: int, tests: str) -> float:
    project.mkdir(exist_ok=True)
    write_django_conftest(project, SYNTHETIC_MODULES % {"modules": modules})
    (project / "test_consumer.py").write_text(tests)
    started = time.perf_counter()
    result = run_rustest(project)
    elapsed = time.perf_counter() - started
    assert result.returncode == 0, result.stdout + result.stderr
    return elapsed


@parametrize("tests", [TESTS, CLASS_TESTS], ids=["functions", "class_methods"])
def test_per_test_cost_does_not_grow_with_loaded_modules(
    tmp_path: Path, tests: str
) -> None:
    baseline = min(
        _timed_run(tmp_path / "small", 10, tests),
        _timed_run(tmp_path / "small", 10, tests),
    )
    crowded = _timed_run(tmp_path / "large", 5000, tests)
    # Both runs execute the same 100 tests; only the number of loaded modules
    # differs. Setup of the crowded run costs a little, so allow a margin.
    assert crowded < baseline * 1.6 + 1.0, (baseline, crowded)
