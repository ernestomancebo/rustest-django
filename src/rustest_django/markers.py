from __future__ import annotations

import inspect
from types import ModuleType

from django.test.utils import isolate_apps
from rustest import FixtureRequest, fixture

from rustest_django._errors import _message


@fixture(autouse=True)
def _django_marker_context(
    _django_isolate_apps,
    _django_set_urlconf,
    _django_template_variables,
    _django_db_isolation,
) -> object:
    """Common activation dependency for all per-test Django marker policies."""
    from rustest_django.marker_activation import _RUNNER_CONTEXT

    return _RUNNER_CONTEXT


@fixture(autouse=True)
def _django_isolate_apps(request: FixtureRequest):
    marker = request.node.get_closest_marker("django_isolate_apps")
    if marker is None:
        yield None
        return
    if (
        marker.kwargs
        or not marker.args
        or any(not isinstance(label, str) or not label for label in marker.args)
    ):
        raise ValueError(
            _message("django_isolate_apps requires one or more app module strings.")
        )
    with isolate_apps(*marker.args) as registry:
        yield registry


@fixture
def django_isolated_apps(_django_isolate_apps):
    if _django_isolate_apps is None:
        raise RuntimeError(
            _message(
                "The django_isolated_apps fixture requires "
                "@mark.django_isolate_apps('app.module', ...)."
            )
        )
    return _django_isolate_apps


@fixture(autouse=True)
def _django_set_urlconf(request: FixtureRequest):
    marker = request.node.get_closest_marker("urls")
    if marker is None:
        yield
        return

    from django.test import override_settings
    from django.urls import clear_url_caches, set_urlconf

    def argument(urls):
        return urls

    try:
        urls = argument(*marker.args, **marker.kwargs)
        if not isinstance(urls, (str, ModuleType)) or not urls:
            raise TypeError
    except TypeError as error:
        raise ValueError(
            _message("urls requires one URLconf module name or module.")
        ) from error

    with override_settings(ROOT_URLCONF=urls):
        clear_url_caches()
        set_urlconf(None)
        try:
            yield
        finally:
            clear_url_caches()
            set_urlconf(None)


class _InvalidTemplateVariable:
    def __contains__(self, value: str) -> bool:
        return value == "%s"

    def __mod__(self, variable) -> str:
        from django.template import Template

        origin = None
        frame = inspect.currentframe()
        try:
            while frame is not None:
                template = frame.f_locals.get("self")
                if isinstance(template, Template):
                    origin = template.origin or template.name
                    break
                frame = frame.f_back
        finally:
            del frame
        detail = f" in '{origin}'" if origin else ""
        raise RuntimeError(
            _message(f"Undefined template variable '{variable}'{detail}")
        )


@fixture(autouse=True)
def _django_template_variables(request: FixtureRequest):
    from django.conf import settings

    from rustest_django import _bootstrap

    marker = request.node.get_closest_marker("ignore_template_errors")
    if marker is not None and (marker.args or marker.kwargs):
        raise ValueError(_message("ignore_template_errors does not accept arguments."))
    config = _bootstrap.resolved_config
    if (
        config is None
        or not config.fail_on_template_vars
        or marker is not None
        or not settings.configured
    ):
        yield
        return

    from django.template import engines
    from django.template.backends.django import DjangoTemplates

    originals = []
    try:
        for backend in engines.all():
            if isinstance(backend, DjangoTemplates):
                engine = backend.engine
                originals.append((engine, engine.string_if_invalid))
                engine.string_if_invalid = _InvalidTemplateVariable()
        yield
    finally:
        for engine, original in reversed(originals):
            engine.string_if_invalid = original
