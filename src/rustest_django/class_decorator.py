from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from rustest import mark

_C = TypeVar("_C", bound=type)


def django_db(*args: Any, **kwargs: Any) -> Callable[[_C], _C]:
    """Class decorator applying ``@mark.django_db(...)`` to every ``test*``
    method, since rustest doesn't propagate a class-level mark to its
    methods (rustest#143). See docs/spec/upstream.md.
    """

    def decorator(cls: _C) -> _C:
        for name, value in list(vars(cls).items()):
            if name.startswith("test") and callable(value):
                setattr(cls, name, mark.django_db(*args, **kwargs)(value))
        return cls

    return decorator
