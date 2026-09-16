from __future__ import annotations

import django.conf
from django.test.utils import setup_test_environment, teardown_test_environment
from rustest import fixture

from rustest_django import _bootstrap


@fixture(autouse=True, scope="session")
def django_test_environment():
    if not django.conf.settings.configured:
        yield
        return

    debug_mode = (
        _bootstrap.resolved_config.debug_mode if _bootstrap.resolved_config else "false"
    )
    debug = None if debug_mode == "keep" else debug_mode == "true"

    setup_test_environment(debug=debug)
    yield
    teardown_test_environment()
