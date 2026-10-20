"""Adapt rustest's public node metadata to fixture-closure discovery.

rustest currently has no request.fixturenames or request.function. Its public
fixture registry and node ID provide the equivalent information without
resolving fixtures or touching the runner's private cache. Finding the test
function and the autouse fixtures means scanning every loaded module, so the
results are cached; see the note above the caches.
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

# TEMPORARY: the caches below exist only because rustest 0.18 has no
# request.fixturenames or request.function (rustest#144). Without them every test
# rescans all of sys.modules, which costs about 20 us per loaded module. Once a
# released rustest provides request.fixturenames (Apex-Engineers-Inc/rustest
# PR #150) and the minimum rustest version is raised, requested_fixtures should
# read request.fixturenames and these caches should be deleted.
#
# The caches are valid while the loaded modules are unchanged. The signature
# below changes when a module is imported, removed or replaced, or when a loaded
# module gains or loses an attribute, which covers a late import and a fixture
# defined after import. Rebinding an existing attribute to a different object
# under the same name is not detected, but autouse discovery only records names
# and the active definition is always looked up again in the registry.
_signature: tuple[int, ...] = ()
_modules_by_path: dict[Path, ModuleType] = {}
_autouse_names: list[str] = []
_resolved_paths: dict[str, Path] = {}
_closures: dict[Any, tuple[dict[str, Callable[..., Any]], list[tuple[str, Any]]]] = {}


def _module_signature() -> tuple[int, ...]:
    signature: list[int] = []
    for module in list(sys.modules.values()):
        signature.append(id(module))
        if type(module) is ModuleType:
            signature.append(len(vars(module)))
    return tuple(signature)


def _refresh_module_caches() -> None:
    global _signature
    signature = _module_signature()
    if signature == _signature:
        return
    _modules_by_path.clear()
    names: set[str] = set()
    for module in list(sys.modules.values()):
        if type(module) is not ModuleType:
            continue
        namespace = vars(module)
        module_path = namespace.get("__file__")
        if module_path:
            resolved = _resolved_paths.get(module_path)
            if resolved is None:
                resolved = Path(module_path).resolve()
                if Path(module_path).is_absolute():
                    _resolved_paths[module_path] = resolved
            _modules_by_path.setdefault(resolved, module)
        for name, candidate in list(namespace.items()):
            if type(candidate) is FunctionType and getattr(
                candidate, "__rustest_fixture_autouse__", False
            ):
                names.add(name)
    _autouse_names[:] = sorted(names)
    _closures.clear()
    _signature = signature


def requested_fixtures(request: FixtureRequest) -> dict[str, Callable[..., Any]]:
    node_path, *identifiers = request.node.nodeid.split("::")
    path = Path(node_path).resolve()
    _refresh_module_caches()
    test: Any = _modules_by_path.get(path)
    if test is not None:
        for identifier in identifiers:
            test = getattr(test, identifier.split("[")[0], None)
    if not callable(test):
        return {}

    marker = request.node.get_closest_marker("usefixtures")
    marked_names = list(marker.args) if marker is not None else []
    for mark in getattr(test, "__rustest_marks__", ()):
        if mark["name"] == "usefixtures":
            marked_names.extend(mark["args"])

    key = (test, tuple(marked_names))
    try:
        cached = _closures.get(key)
    except TypeError:
        return _closure(test, marked_names)[0]
    if cached is not None:
        result, lookups = cached
        if all(_active(name) is definition for name, definition in lookups):
            return dict(result)
    result, lookups = _closure(test, marked_names)
    _closures[key] = (result, lookups)
    return dict(result)


def _active(name: str) -> Any:
    try:
        return get_fixture(name)
    except ValueError:
        return None


def _closure(
    test: Any, marked_names: list[str]
) -> tuple[dict[str, Callable[..., Any]], list[tuple[str, Any]]]:
    names: set[str] = set()
    definitions: dict[str, Callable[..., Any]] = {}
    # Every registry lookup made while building the closure, so a later call can
    # confirm the registry still answers the same way before reusing the result.
    lookups: list[tuple[str, Any]] = []
    direct_parameters = {
        name
        for case in getattr(test, "__rustest_parametrization__", ())
        for name in case["values"]
    } - set(getattr(test, "__rustest_parametrization_indirect__", ()))

    def lookup(name: str) -> Any:
        dependency = _active(name)
        lookups.append((name, dependency))
        return dependency

    def visit(function) -> None:
        for name in inspect.signature(function).parameters:
            if name in names or name in direct_parameters:
                continue
            names.add(name)
            dependency = lookup(name)
            if dependency is None:
                continue
            definitions[name] = dependency
            visit(dependency)

    visit(test)
    for name in marked_names:
        if name in names or name in direct_parameters:
            continue
        names.add(name)
        dependency = lookup(name)
        if dependency is None:
            continue
        definitions[name] = dependency
        visit(dependency)
    # The registry has no listing API. Discover decorator metadata on loaded
    # functions, then ask the public registry for the active definition so
    # overrides and fixtures from unrelated modules cannot change this test.
    for name in _autouse_names:
        active = lookup(name)
        if active is not None and getattr(active, "__rustest_fixture_autouse__", False):
            definitions[name] = active
            visit(active)
    return definitions, lookups
