from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, overload

from rustest import mark

_C = TypeVar("_C", bound=type)


@overload
def django_db(cls: _C, /) -> _C: ...


@overload
def django_db(*args: Any, **kwargs: Any) -> Callable[[_C], _C]: ...


def django_db(*args: Any, **kwargs: Any) -> Any:
    """Class decorator applying ``@mark.django_db(...)`` to every ``test*``
    method, since rustest doesn't propagate a class-level mark to its
    methods (rustest#143). See docs/spec/upstream.md.

    Works both bare (``@django_db``) and called (``@django_db(...)``), like
    ``@pytest.mark.django_db``.
    """
    if len(args) == 1 and not kwargs:
        target = args[0]
        if isinstance(target, type):
            return django_db()(target)
        if callable(target):
            raise TypeError(
                "django_db decorates classes only; use @django_db or "
                "@django_db() on a class (for a function, use "
                "@mark.django_db)"
            )

    def decorator(cls: _C) -> _C:
        for name, value in list(vars(cls).items()):
            if name.startswith("test") and callable(value):
                setattr(cls, name, mark.django_db(*args, **kwargs)(value))
        return cls

    return decorator
