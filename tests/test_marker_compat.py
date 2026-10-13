import re
import textwrap
from pathlib import Path

from _helpers import run_rustest
from rustest import parametrize


def _project(project: Path, tests: str) -> None:
    (project / "conftest.py").write_text(
        textwrap.dedent(
            """
            import django
            from django.conf import settings

            settings.configure(
                SECRET_KEY="test-secret",
                INSTALLED_APPS=["django.contrib.contenttypes"],
                DATABASES={"default": {
                    "ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:",
                }},
                ROOT_URLCONF="original_urls",
                TEMPLATES=[{
                    "BACKEND": "django.template.backends.django.DjangoTemplates",
                    "OPTIONS": {},
                }],
            )
            django.setup()
            rustest_fixtures = ["rustest_django"]
            """
        )
    )
    (project / "original_urls.py").write_text(
        "from django.http import HttpResponse\n"
        "from django.urls import path\n"
        'urlpatterns = [path("value/", lambda request: HttpResponse("original"))]\n'
    )
    (project / "test_consumer.py").write_text(textwrap.dedent(tests))


def test_app_isolation_exposes_registry_without_leaking_models(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from django.apps import apps
        from django.db import models
        from rustest import mark

        @mark.django_isolate_apps("django.contrib.contenttypes")
        def test_01_isolated(django_isolated_apps):
            class Temporary(models.Model):
                class Meta:
                    app_label = "contenttypes"
            assert (
                django_isolated_apps.get_model("contenttypes", "Temporary") is Temporary
            )
            assert Temporary._meta.apps is django_isolated_apps

        def test_02_restored():
            assert list(apps.get_app_config("contenttypes").get_models()) == [
                apps.get_model("contenttypes", "ContentType")
            ]
            class Later(models.Model):
                class Meta:
                    app_label = "contenttypes"
            assert Later._meta.apps is apps
        """,
    )
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@parametrize("arguments", ["", "42", 'unknown="django.contrib.contenttypes"'])
def test_app_isolation_rejects_invalid_app_labels(
    tmp_path: Path, arguments: str
) -> None:
    _project(
        tmp_path,
        f"""
        from rustest import mark

        @mark.django_isolate_apps({arguments})
        def test_invalid_marker():
            pass
        """,
    )
    result = run_rustest(tmp_path)
    assert result.returncode != 0, result.stdout + result.stderr
    expected = "django_isolate_apps requires one or more app module strings"
    assert expected in result.stderr


def test_urls_marker_overrides_warm_resolvers_and_restores_settings(
    tmp_path: Path,
) -> None:
    _project(
        tmp_path,
        """
        from django.urls import resolve, set_urlconf
        from rustest import mark

        def test_01_warm_original_resolver(client):
            assert client.get("/value/").content == b"original"
            set_urlconf("original_urls")
            assert resolve("/value/").func(None).content == b"original"

        @mark.urls("alternate_urls")
        def test_02_override(client):
            assert client.get("/value/").content == b"alternate"
            assert resolve("/value/").func(None).content == b"alternate"

        def test_03_restored(client):
            assert client.get("/value/").content == b"original"
            assert resolve("/value/").func(None).content == b"original"
        """,
    )
    (tmp_path / "alternate_urls.py").write_text(
        "from django.http import HttpResponse\n"
        "from django.urls import path\n"
        'urlpatterns = [path("value/", lambda request: HttpResponse("alternate"))]\n'
    )
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@parametrize("arguments", ["", "42", 'invalid="original_urls"'])
def test_urls_marker_rejects_invalid_arguments(tmp_path: Path, arguments: str) -> None:
    _project(
        tmp_path,
        f"""
        from rustest import mark

        @mark.urls({arguments})
        def test_invalid_marker():
            pass
        """,
    )
    result = run_rustest(tmp_path)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "urls requires one URLconf module name or module" in result.stderr


def test_template_error_exemption_preserves_normal_rendering(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from django.template import engines
        from rustest import mark

        @mark.ignore_template_errors
        def test_exempt_render():
            template = engines["django"].from_string('{{ absent|default:"fallback" }}')
            assert template.render({}) == "fallback"
        """,
    )
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_strict_templates_fail_missing_variables_but_allow_conditionals(
    tmp_path: Path,
) -> None:
    _project(
        tmp_path,
        """
        from django.template import engines

        def test_01_missing_variable():
            engines["django"].from_string("{{ missing.title }}").render({})

        def test_02_missing_condition_is_allowed():
            template = engines["django"].from_string(
                "{% if missing %}present{% else %}absent{% endif %}"
            )
            assert template.render({}) == "absent"
        """,
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.rustest-django]\nfail_on_template_vars = true\n"
    )
    result = run_rustest(tmp_path)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "Undefined template variable 'missing.title'" in result.stderr
    assert "1 passed" in result.stderr
    assert "1 failed" in result.stderr


def test_strict_template_error_reports_file_for_filtered_missing_variable(
    tmp_path: Path,
) -> None:
    _project(
        tmp_path,
        """
        from django.template.loader import render_to_string

        def test_render_broken_template():
            render_to_string("broken.html", {})
        """,
    )
    (tmp_path / "broken.html").write_text('{{ missing|default:"fallback" }}')
    with (tmp_path / "conftest.py").open("a") as conftest:
        conftest.write(
            "from pathlib import Path\n"
            'settings.TEMPLATES[0]["DIRS"] = [str(Path(__file__).parent)]\n'
        )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.rustest-django]\nfail_on_template_vars = true\n"
    )
    result = run_rustest(tmp_path)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "Undefined template variable 'missing'" in result.stderr
    assert re.search(
        r"Undefined template variable 'missing' in '[^']*broken\.html'",
        result.stderr,
    ), result.stderr


def test_template_exemption_rejects_arguments(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from rustest import mark

        @mark.ignore_template_errors(enabled=True)
        def test_invalid_exemption():
            pass
        """,
    )
    result = run_rustest(tmp_path)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "ignore_template_errors does not accept arguments" in result.stderr


def test_strict_template_setting_allows_tests_without_django_settings(
    tmp_path: Path,
) -> None:
    (tmp_path / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (tmp_path / "pyproject.toml").write_text(
        "[tool.rustest-django]\nfail_on_template_vars = true\n"
    )
    (tmp_path / "test_consumer.py").write_text("def test_plain_python():\n    pass\n")
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_marker_state_is_restored_after_test_and_fixture_failures(
    tmp_path: Path,
) -> None:
    _project(
        tmp_path,
        """
        from django.apps import apps
        from django.db import models
        from django.template import engines
        from django.urls import resolve
        from rustest import fixture, mark

        @fixture
        def broken():
            raise RuntimeError("deliberate fixture failure")

        @mark.django_isolate_apps("django.contrib.contenttypes")
        @mark.urls("alternate_urls")
        def test_01_body_fails():
            class Temporary(models.Model):
                class Meta:
                    app_label = "contenttypes"
            assert False, "deliberate test failure"

        @mark.django_isolate_apps("django.contrib.contenttypes")
        @mark.urls("alternate_urls")
        def test_02_fixture_fails(broken):
            pass

        @mark.ignore_template_errors
        def test_03_restored():
            assert resolve("/value/").func(None).content == b"original"
            class Later(models.Model):
                class Meta:
                    app_label = "contenttypes"
            assert Later._meta.apps is apps
            template = engines["django"].from_string('{{ missing|default:"fallback" }}')
            assert template.render({}) == "fallback"
        """,
    )
    (tmp_path / "alternate_urls.py").write_text("urlpatterns = []\n")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.rustest-django]\nfail_on_template_vars = true\n"
    )
    result = run_rustest(tmp_path)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "deliberate fixture failure" in result.stderr
    assert "deliberate test failure" in result.stderr
    assert "1 passed" in result.stderr
    assert "2 failed" in result.stderr
