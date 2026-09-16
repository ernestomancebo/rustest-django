from __future__ import annotations

from collections.abc import Callable
from typing import Any, NoReturn

from django.db.backends.base.base import BaseDatabaseWrapper


def _blocking_wrapper(*args: Any, **kwargs: Any) -> NoReturn:
    raise RuntimeError(
        "Database access not allowed, use the django_db mark, or the "
        "db or transactional_db fixtures to enable it."
    )


class _RestoreOnExit:
    def __init__(self, blocker: DjangoDbBlocker) -> None:
        self._blocker = blocker

    def __enter__(self) -> None:
        pass

    def __exit__(self, *exc_info: object) -> None:
        self._blocker.restore()


class DjangoDbBlocker:
    def __init__(self) -> None:
        self._history: list[Callable[..., Any]] = []
        self._real_ensure_connection = BaseDatabaseWrapper.ensure_connection

    def _save_active_wrapper(self) -> None:
        self._history.append(BaseDatabaseWrapper.ensure_connection)

    def block(self) -> _RestoreOnExit:
        self._save_active_wrapper()
        BaseDatabaseWrapper.ensure_connection = _blocking_wrapper
        return _RestoreOnExit(self)

    def unblock(self) -> _RestoreOnExit:
        self._save_active_wrapper()
        BaseDatabaseWrapper.ensure_connection = self._real_ensure_connection
        return _RestoreOnExit(self)

    def restore(self) -> None:
        BaseDatabaseWrapper.ensure_connection = self._history.pop()

    @property
    def is_active(self) -> bool:
        return bool(self._history)
