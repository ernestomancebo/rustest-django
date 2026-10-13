"""Execute the public examples used to grade the agent skills."""

import os
import re
import subprocess
import sys
from pathlib import Path

from rustest import mark

EVALS = Path(__file__).resolve().parents[1] / "skills" / "evals"


def _run_example(
    project: Path, case: str, block: int = 0, *, pytest_compat: bool = False
) -> subprocess.CompletedProcess[str]:
    prompt = (EVALS / case / "prompt.md").read_text()
    source = re.findall(r"```python\n(.*?)```", prompt, re.DOTALL)[block]
    (project / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (project / "pyproject.toml").write_text(
        '[tool.rustest-django]\nsettings_module = "settings"\n'
    )
    (project / "settings.py").write_text(
        'SECRET_KEY = "test-secret-key"\n'
        'INSTALLED_APPS = ["blog"]\n'
        'DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", '
        '"NAME": ":memory:"}}\n'
    )
    app = project / "blog"
    app.mkdir()
    (app / "__init__.py").write_text("")
    (app / "models.py").write_text(
        "from django.db import models\n"
        "class Post(models.Model):\n"
        "    title = models.CharField(max_length=100)\n"
    )
    (project / "test_example.py").write_text(source)
    command = [sys.executable, "-m", "rustest", "--color=never"]
    if pytest_compat:
        command.append("--pytest-compat")
    command.append(str(project / "test_example.py"))
    return subprocess.run(
        command,
        cwd=project,
        capture_output=True,
        text=True,
        env={**os.environ, "COLUMNS": "300"},
        timeout=30,
    )


@mark.parametrize("block,pytest_compat", [(0, False), (1, True)])
def test_database_diagnosis_examples_fail_with_database_access_error(
    tmp_path: Path, block: int, pytest_compat: bool
) -> None:
    result = _run_example(
        tmp_path, "doctor-disambiguates-db-error", block, pytest_compat=pytest_compat
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert "Database access not allowed" in result.stderr, result.stdout + result.stderr


def test_skip_diagnosis_example_fails_with_unittest_skiptest(tmp_path: Path) -> None:
    result = _run_example(tmp_path, "doctor-skiptest-no-workaround")

    assert result.returncode != 0, result.stdout + result.stderr
    assert "SkipTest" in result.stderr, result.stdout + result.stderr
