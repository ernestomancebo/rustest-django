from __future__ import annotations

from pathlib import Path

import django.test
from rustest import FixtureRequest, fail, fixture

from rustest_django._errors import _message
from rustest_django.rustest_compat import module_for_path


def _resolve_test_class(node: object) -> type | None:
    # rustest's node exposes no `.cls`; the class name is embedded in
    # `.name` as "ClassName::method_name", so the class itself has to be
    # found by matching the test file to an already-imported module.
    name = getattr(node, "name", "")
    if "::" not in name:
        return None
    class_name, _, _ = name.partition("::")

    nodeid = getattr(node, "nodeid", "")
    file_path = nodeid.split("::")[0]
    if not file_path:
        return None
    module = module_for_path(Path(file_path).resolve())
    if module is None:
        return None
    return getattr(module, class_name, None)


@fixture(autouse=True)
def _unittest_style_guard(request: FixtureRequest) -> None:
    test_class = _resolve_test_class(request.node)
    if test_class is not None and issubclass(test_class, django.test.SimpleTestCase):
        fail(
            _message(
                f"{test_class.__module__}.{test_class.__qualname__} is a "
                "unittest-style Django TestCase (SimpleTestCase/TestCase/"
                "TransactionTestCase/LiveServerTestCase), which is "
                "unsupported in rustest-django v1: rustest discards its "
                "result, so every method would otherwise silently report "
                "as passed. Use plain functions with the db/transactional_db "
                "fixtures instead."
            )
        )
