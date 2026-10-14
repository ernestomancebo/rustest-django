"""Execute the public examples used to grade the agent skills."""

import os
import re
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

from rustest import mark

EVALS = Path(__file__).resolve().parents[1] / "skills" / "evals"
ROOT = EVALS.parents[1]


def test_eval_judge_receives_request_constraints_and_public_api(tmp_path: Path) -> None:
    prepared = tmp_path / "skills"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_skill_evals.py"),
            "--prepare-only",
            str(prepared),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    legacy = prepared / "evals" / "doctor-preserves-migration-data"
    criteria = (legacy / "graders" / "criteria.md").read_text()
    assert "upgrading is outside this request" in criteria
    live = prepared / "evals" / "migrate-live-server-transactions"
    assert 'live_server + "/path/"' in (live / "graders" / "criteria.md").read_text()
    for case in EVALS.glob("*/prompt.md"):
        assert (prepared / "evals" / case.parent.name / "prompt.md").read_bytes() == (
            case.read_bytes()
        )
    indicator = "doctor-preserves-migration-data/graders/skill-fired.md"
    assert (prepared / "evals" / indicator).read_bytes() == (
        EVALS / indicator
    ).read_bytes()


def _run_example(
    project: Path,
    case: str,
    block: int = 0,
    *,
    pytest_compat: bool = False,
    source: str | None = None,
) -> subprocess.CompletedProcess[str]:
    if source is None:
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
        'TEMPLATES = [{"BACKEND": '
        '"django.template.backends.django.DjangoTemplates"}]\n'
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


@mark.parametrize("supports_json", [True, False])
def test_documented_skip_replacement_preserves_the_backend_condition(
    tmp_path: Path, supports_json: bool
) -> None:
    skill = (EVALS.parent / "rustest-django-doctor" / "SKILL.md").read_text()
    examples = re.findall(r"```python\n(.*?)```", skill, re.DOTALL)
    source = dedent(
        next(example for example in examples if "supports_json_field" in example)
    )
    source = (
        "from django.db import connection as test_backend\n"
        f"test_backend.features.supports_json_field = {supports_json!r}\n\n" + source
    )
    result = _run_example(tmp_path, "doctor-skiptest-no-workaround", source=source)
    output = result.stdout + result.stderr
    if supports_json:
        assert result.returncode == 0, output
        assert "1 skipped" in output, output
    else:
        assert result.returncode != 0, output
        assert "1 failed" in output, output
        assert "This path is only for backends without JSON fields" in output, output


def test_template_diagnosis_example_fails_on_missing_rendered_variable(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("RUSTEST_DJANGO_FAIL_ON_TEMPLATE_VARS", "true")
    result = _run_example(tmp_path, "doctor-template-fixture-policy")

    assert result.returncode != 0, result.stdout + result.stderr
    assert "Undefined template variable 'missing'" in result.stderr, (
        result.stdout + result.stderr
    )


def test_app_registry_diagnosis_example_requires_companion_marker(
    tmp_path: Path,
) -> None:
    result = _run_example(tmp_path, "doctor-isolated-app-registry")

    assert result.returncode != 0, result.stdout + result.stderr
    assert "django_isolated_apps fixture requires" in result.stderr, (
        result.stdout + result.stderr
    )
