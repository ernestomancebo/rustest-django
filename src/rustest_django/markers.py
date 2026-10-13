from __future__ import annotations

from types import ModuleType

from django.test.utils import isolate_apps
from rustest import FixtureRequest, fixture

from rustest_django._errors import _message


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
