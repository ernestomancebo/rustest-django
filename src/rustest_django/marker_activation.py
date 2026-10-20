"""Activate marker fixtures before rustest resolves consumer fixture arguments.

rustest 0.18 resolves named arguments before autouse fixtures. The public import
loader boundary lets the plugin prepend a normal fixture dependency to collected
tests, keeping setup, caching, and teardown in the runner's fixture machinery.
"""

from __future__ import annotations

import inspect
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import FunctionType, ModuleType
from typing import cast

from rustest import run

_CONTEXT = "_django_marker_context"
_RUNNER_CONTEXT = object()
_UNSET = object()


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
    parameters = list(signature.parameters.values())
    receiver = class_owner is not None or (parameters and parameters[0].name == "self")
    if receiver and class_owner is None:
        parameters = parameters[1:]
    concrete = [
        parameter
        for parameter in parameters
        if parameter.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]
    names = [parameter.name for parameter in concrete]
    args_name = "_activation_args"
    kwargs_name = "_activation_kwargs"
    while args_name in names:
        args_name += "_"
    while kwargs_name in names:
        kwargs_name += "_"

    def invoke(bound_receiver, values, extra, keywords):
        active_target = (
            function.__get__(bound_receiver, type(bound_receiver))
            if class_owner is not None
            else function
        )
        positional = [bound_receiver] if receiver and class_owner is None else []
        if values[0] is _RUNNER_CONTEXT:
            for parameter, value in zip(concrete, values[1:], strict=True):
                if parameter.kind is inspect.Parameter.KEYWORD_ONLY:
                    keywords[parameter.name] = value
                else:
                    positional.append(value)
        else:
            positional.extend(value for value in values if value is not _UNSET)
        positional.extend(extra)
        return active_target(*positional, **keywords)

    # Positional-only slots keep all ordinary caller keywords untouched. The
    # runner supplies a unique first token; direct Python calls never need one.
    slots = [_CONTEXT, *names]
    declaration = ["self"] if receiver else []
    declaration.extend(f"{name}=_unset" for name in slots)
    declaration.extend(["/", f"*{args_name}", f"**{kwargs_name}"])
    receiver_expression = "self" if receiver else "None"
    prefix = "async " if inspect.iscoroutinefunction(function) else ""
    await_prefix = "await " if prefix else ""
    namespace = {"_invoke": invoke, "_unset": _UNSET}
    source = (
        f"{prefix}def activated({', '.join(declaration)}):\n"
        f"    return {await_prefix}_invoke({receiver_expression}, "
        f"({', '.join(slots)},), {args_name}, {kwargs_name})\n"
    )
    exec(compile(source, __file__, "exec"), namespace)  # noqa: S102
    activated = cast(FunctionType, namespace["activated"])
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
    test_path = Path(path).resolve()
    for loaded in list(sys.modules.values()):
        if type(loaded) is not ModuleType:
            continue
        attributes = vars(loaded)
        # Check the cheap attribute first so Path work only happens for the
        # few modules that declare rustest_fixtures.
        plugins = attributes.get("rustest_fixtures", ())
        conftest = attributes.get("__file__")
        if (
            isinstance(plugins, (list, tuple))
            and "rustest_django" in plugins
            and conftest
            and Path(conftest).name == "conftest.py"
            and test_path.is_relative_to(Path(conftest).resolve().parent)
        ):
            break
    else:
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
