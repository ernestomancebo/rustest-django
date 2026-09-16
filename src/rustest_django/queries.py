from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from functools import partial
from typing import Any, Protocol

import django.test
from django.db import connection as default_connection
from django.db import connections
from django.test.utils import CaptureQueriesContext
from rustest import fail, fixture


class DjangoAssertNumQueries(Protocol):
    def __call__(
        self,
        num: int,
        connection: Any | None = ...,
        info: str | None = ...,
        *,
        using: str | None = ...,
    ) -> AbstractContextManager[CaptureQueriesContext]: ...


class DjangoCaptureOnCommitCallbacks(Protocol):
    def __call__(
        self, *, using: str = ..., execute: bool = ...
    ) -> AbstractContextManager[list[Callable[[], Any]]]: ...


@contextmanager
def _assert_num_queries(
    num: int,
    exact: bool = True,
    connection: Any | None = None,
    info: str | None = None,
    *,
    using: str | None = None,
) -> Generator[CaptureQueriesContext]:
    if connection and using:
        raise ValueError(
            'The "connection" and "using" parameter cannot be used together'
        )

    if connection is not None:
        conn = connection
    elif using is not None:
        conn = connections[using]
    else:
        conn = default_connection

    with CaptureQueriesContext(conn) as context:
        yield context
        num_performed = len(context)
        failed = num != num_performed if exact else num_performed > num
        if failed:
            msg = f"Expected to perform {num} queries "
            if not exact:
                msg += "or less "
            verb = "was" if num_performed == 1 else "were"
            msg += f"but {num_performed} {verb} done"
            if info:
                msg += f"\n{info}"
            sqls = (q["sql"] for q in context.captured_queries)
            msg += "\n\nQueries:\n========\n\n" + "\n\n".join(sqls)
            fail(msg)


@fixture
def django_assert_num_queries():
    return partial(_assert_num_queries)


@fixture
def django_assert_max_num_queries():
    return partial(_assert_num_queries, exact=False)


@fixture
def django_capture_on_commit_callbacks():
    return django.test.TestCase.captureOnCommitCallbacks
