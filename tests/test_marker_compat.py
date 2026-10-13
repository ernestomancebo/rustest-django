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
