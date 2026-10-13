"""Adapt rustest's public node metadata to fixture-closure discovery.

rustest currently has no request.fixturenames or request.function. Its public
fixture registry and node ID provide the equivalent information without
resolving fixtures or touching the runner's private cache.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import FunctionType, ModuleType

from rustest import FixtureRequest
from rustest.fixture_registry import get_fixture


def requested_fixtures(request: FixtureRequest) -> set[str]:
    node_path, *identifiers = request.node.nodeid.split("::")
    path = Path(node_path).resolve()
    test = None
    for module in list(sys.modules.values()):
        if type(module) is not ModuleType:
            continue
        module_path = vars(module).get("__file__")
        if module_path and Path(module_path).resolve() == path:
            test = module
            for identifier in identifiers:
                test = getattr(test, identifier.split("[")[0], None)
            break
    if not callable(test):
        return set()

    names: set[str] = set()

    def visit(function) -> None:
        for name in inspect.signature(function).parameters:
            if name in names:
                continue
            names.add(name)
            try:
                dependency = get_fixture(name)
            except ValueError:
                continue
            visit(dependency)

    visit(test)
    # The registry has no listing API. Discover decorator metadata on loaded
    # functions, then ask the public registry for the active definition so
    # overrides and fixtures from unrelated modules cannot change this test.
    for module in list(sys.modules.values()):
        if type(module) is not ModuleType:
            continue
        for name, candidate in list(vars(module).items()):
            if type(candidate) is not FunctionType or not getattr(
                candidate, "__rustest_fixture_autouse__", False
            ):
                continue
            try:
                active = get_fixture(name)
            except ValueError:
                continue
            if getattr(active, "__rustest_fixture_autouse__", False):
                visit(active)
    return names
