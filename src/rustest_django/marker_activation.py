"""Activate marker fixtures before rustest resolves consumer fixture arguments.

rustest 0.18 resolves named arguments before autouse fixtures. The public import
loader boundary lets the plugin prepend a normal fixture dependency to collected
tests, keeping setup, caching, and teardown in the runner's fixture machinery.
"""

from __future__ import annotations

import inspect
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import FunctionType, ModuleType

from rustest import run

_CONTEXT = "_django_marker_context"


def _running_rustest() -> bool:
    frame = inspect.currentframe()
    try:
        while frame is not None:
            if frame.f_code is run.__code__:
                return True
            frame = frame.f_back
        return False
    finally:
        del frame


def _activate_test(function: FunctionType, *, class_owner: type | None = None):
    if getattr(function, "__rustest_fixture__", False):
        return function
    if getattr(function, "__rustest_django_activation__", False):
        if (
            class_owner is None
            or getattr(function, "__rustest_django_class_owner__", None) is class_owner
        ):
            return function
        function = function.__dict__["__wrapped__"]
    target = (
        function.__get__(class_owner, type(class_owner)) if class_owner else function
    )
    signature = inspect.signature(target)
    parameters = []
    defaults = []
    variadics = []
    namespace = {"_test": target}
    arguments = []
    for index, parameter in enumerate(signature.parameters.values()):
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY:
            arguments.append(f"{parameter.name}={parameter.name}")
        elif parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            arguments.append(f"*{parameter.name}")
        elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
            arguments.append(f"**{parameter.name}")
        else:
            arguments.append(parameter.name)
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            variadics.append(f"*{parameter.name}")
        elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
            variadics.append(f"**{parameter.name}")
        elif parameter.default is inspect.Parameter.empty:
            parameters.append(parameter.name)
        else:
            default_name = f"_default_{index}"
            namespace[default_name] = parameter.default
            defaults.append(f"{parameter.name}={default_name}")
    arguments = ", ".join(arguments)
    if class_owner is not None:
        parameters.insert(0, "self")
    index = 1 if parameters and parameters[0] == "self" else 0
    parameters.insert(index, _CONTEXT)
    parameters.extend(defaults)
    parameters.extend(variadics)
    prefix = "async " if inspect.iscoroutinefunction(function) else ""
    await_prefix = "await " if prefix else ""
    source = (
        f"{prefix}def activated({', '.join(parameters)}):\n"
        f"    return {await_prefix}_test({arguments})\n"
    )
    exec(compile(source, __file__, "exec"), namespace)  # noqa: S102
    activated = namespace["activated"]
    activated.__dict__.update(function.__dict__)
    activated.__name__ = function.__name__
    activated.__qualname__ = function.__qualname__
    activated.__module__ = function.__module__
    activated.__doc__ = function.__doc__
    activated.__dict__["__wrapped__"] = function
    activated.__dict__["__rustest_django_activation__"] = True
    activated.__dict__["__rustest_django_class_owner__"] = class_owner
    return activated


def _activate_module(module: ModuleType) -> None:
    path = getattr(module, "__file__", None)
    if path is None:
        return
    stem = Path(path).stem
    if not (stem.startswith("test_") or stem.endswith("_test")):
        return
    for name, candidate in list(vars(module).items()):
        if name.startswith("test") and isinstance(candidate, FunctionType):
            setattr(module, name, _activate_test(candidate))
        elif isinstance(candidate, type) and candidate.__module__ == module.__name__:
            for method_name in dir(candidate):
                if not method_name.startswith("test"):
                    continue
                method = inspect.getattr_static(candidate, method_name)
                if isinstance(method, FunctionType):
                    replacement = _activate_test(method)
                elif isinstance(method, classmethod):
                    replacement = classmethod(
                        _activate_test(method.__func__, class_owner=candidate)
                    )
                elif isinstance(method, staticmethod):
                    replacement = staticmethod(_activate_test(method.__func__))
                else:
                    continue
                setattr(candidate, method_name, replacement)


def install() -> None:
    original = SourceFileLoader.exec_module
    if getattr(original, "__rustest_django_activation__", False):
        return

    def execute(self, module: ModuleType) -> None:
        original(self, module)
        if _running_rustest():
            _activate_module(module)

    execute.__dict__["__rustest_django_activation__"] = True
    SourceFileLoader.exec_module = execute
