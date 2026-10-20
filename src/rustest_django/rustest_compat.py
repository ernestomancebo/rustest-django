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


class _LoadedModules:
    """Index of the loaded modules, rebuilt when the set of loaded modules changes.

    TEMPORARY: rustest 0.18 has no request.fixturenames or request.function
    (rustest#144), so finding a test's module and the autouse fixtures means
    scanning all of sys.modules, which costs about 20 us per loaded module per
    test. Apex-Engineers-Inc/rustest PR #150 adds request.fixturenames only, so
    the path index stays until rustest also exposes the test's function or
    module; unittest_guard needs it to find a test's class from its node ID. The
    autouse discovery goes away with request.fixturenames.

    The signature changes when a module is imported, removed or replaced, or when
    a loaded module gains or loses an attribute, which covers a late import and a
    fixture defined after import. Rebinding an existing attribute to a different
    object under the same name is not detected, but autouse discovery only
    records names and the active definition is always looked up in the registry.
    """

    def __init__(self) -> None:
        self.clear()

    def clear(self) -> None:
        self._signature: tuple[int, ...] | None = None
        self._by_path: dict[Path, ModuleType] = {}
        self._autouse_names: list[str] | None = None
        self._resolved: dict[str, Path] = {}

    def refresh(self) -> None:
        signature: list[int] = []
        for module in list(sys.modules.values()):
            signature.append(id(module))
            if type(module) is ModuleType:
                signature.append(len(vars(module)))
        current = tuple(signature)
        if current == self._signature:
            return
        self._signature = current
        self._autouse_names = None
        self._by_path = {}
        for module in list(sys.modules.values()):
            if type(module) is not ModuleType:
                continue
            module_path = vars(module).get("__file__")
            if module_path:
                self._by_path.setdefault(self._resolve(module_path), module)

    def _resolve(self, module_path: str) -> Path:
        resolved = self._resolved.get(module_path)
        if resolved is None:
            path = Path(module_path)
            resolved = path.resolve()
            # A relative path resolves against the current directory, which can
            # change, so only absolute paths are remembered.
            if path.is_absolute():
                self._resolved[module_path] = resolved
        return resolved

    def module_for_path(self, path: Path) -> ModuleType | None:
        self.refresh()
        return self._by_path.get(path)

    # TODO(rustest#144): delete once request.fixturenames is released and required.
    def autouse_names(self) -> list[str]:
        self.refresh()
        if self._autouse_names is None:
            names: set[str] = set()
            for module in list(sys.modules.values()):
                if type(module) is not ModuleType:
                    continue
                for name, candidate in list(vars(module).items()):
                    if type(candidate) is FunctionType and getattr(
                        candidate, "__rustest_fixture_autouse__", False
                    ):
                        names.add(name)
            self._autouse_names = sorted(names)
        return self._autouse_names


_loaded_modules = _LoadedModules()


def module_for_path(path: Path) -> ModuleType | None:
    """Return the first loaded module whose file resolves to ``path``."""
    return _loaded_modules.module_for_path(path)


def _active(name: str) -> Any:
    try:
        return get_fixture(name)
    except ValueError:
        return None


def requested_fixtures(request: FixtureRequest) -> dict[str, Callable[..., Any]]:
    node_path, *identifiers = request.node.nodeid.split("::")
    path = Path(node_path).resolve()
    test: Any = module_for_path(path)
    if test is not None:
        for identifier in identifiers:
            test = getattr(test, identifier.split("[")[0], None)
    if not callable(test):
        return {}

    names: set[str] = set()
    definitions: dict[str, Callable[..., Any]] = {}
    direct_parameters = {
        name
        for case in getattr(test, "__rustest_parametrization__", ())
        for name in case["values"]
    } - set(getattr(test, "__rustest_parametrization_indirect__", ()))

    def request_fixture(name: str) -> None:
        if name in names or name in direct_parameters:
            return
        names.add(name)
        dependency = _active(name)
        if dependency is None:
            return
        definitions[name] = dependency
        visit(dependency)

    def visit(function) -> None:
        for name in inspect.signature(function).parameters:
            request_fixture(name)

    visit(test)
    marker = request.node.get_closest_marker("usefixtures")
    marked_names = list(marker.args) if marker is not None else []
    for mark in getattr(test, "__rustest_marks__", ()):
        if mark["name"] == "usefixtures":
            marked_names.extend(mark["args"])
    for name in marked_names:
        request_fixture(name)
    # TODO(rustest#144): delete once request.fixturenames is released and required.
    # The registry has no listing API. Discover decorator metadata on loaded
    # functions, then ask the public registry for the active definition so
    # overrides and fixtures from unrelated modules cannot change this test.
    for name in _loaded_modules.autouse_names():
        active = _active(name)
        if active is not None and getattr(active, "__rustest_fixture_autouse__", False):
            definitions[name] = active
            visit(active)
    return definitions
