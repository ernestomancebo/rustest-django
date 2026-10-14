"""Adapt rustest's public node metadata to fixture-closure discovery.

rustest currently has no request.fixturenames or request.function. Its public
fixture registry and node ID provide the equivalent information without
resolving fixtures or touching the runner's private cache.
"""

from __future__ import annotations

import inspect
import sys
from collections.abc import Callable
from pathlib import Path
from types import FunctionType, ModuleType
from typing import Any

from rustest import FixtureRequest
from rustest.fixture_registry import get_fixture


def requested_fixtures(request: FixtureRequest) -> dict[str, Callable[..., Any]]:
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
        return {}

    names: set[str] = set()
    definitions: dict[str, Callable[..., Any]] = {}
    direct_parameters = {
        name
        for case in getattr(test, "__rustest_parametrization__", ())
        for name in case["values"]
    } - set(getattr(test, "__rustest_parametrization_indirect__", ()))

    def visit(function) -> None:
        for name in inspect.signature(function).parameters:
            if name in names or name in direct_parameters:
                continue
            names.add(name)
            try:
                dependency = get_fixture(name)
            except ValueError:
                continue
            definitions[name] = dependency
            visit(dependency)

    visit(test)
    marker = request.node.get_closest_marker("usefixtures")
    marked_names = list(marker.args) if marker is not None else []
    for mark in getattr(test, "__rustest_marks__", ()):
        if mark["name"] == "usefixtures":
            marked_names.extend(mark["args"])
    for name in marked_names:
        if name in names or name in direct_parameters:
            continue
        names.add(name)
        try:
            dependency = get_fixture(name)
        except ValueError:
            continue
        definitions[name] = dependency
        visit(dependency)
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
                definitions[name] = active
                visit(active)
    return definitions
