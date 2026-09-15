# Async support

Spec section for rustest-django v1. Decided in wayfinder ticket #11.

rustest runs async tests natively: a coroutine test function needs no marker, and gets
its own event loop when every fixture it uses is sync. The test coroutine runs on the
main thread; rustest adds no threads of its own.

## Fixtures

- `async_client`: sync fixture returning `django.test.AsyncClient()`.
- `async_rf`: sync fixture returning `django.test.AsyncRequestFactory()`.
- No fixture in rustest-django is `async def`. This keeps every test's loop scope at
  `function`, so rustest never batches tests onto a shared loop.

## Database access from async tests

Allowed, with pytest-django's caveat reproduced verbatim: `db`, `transactional_db` and
the `django_db` marker work on async tests, but ORM calls wrapped in `sync_to_async`
(including sync views driven through `async_client`) run on asgiref's executor thread and
use a different Django connection than the one the isolation opened. Rollback isolation
may not cover those calls, and an in-memory SQLite database may not be the same database
at all. Consumers use `transactional_db` or a file-backed test database for such tests,
as they do under pytest-django.

## Loop scope

Wider loop scopes (a consumer `async def` fixture at class, module or session scope, or
`asyncio_default_test_loop_scope` set in `pyproject.toml`) make rustest run those tests
concurrently on one loop, interleaving database transactions at `await` points. This is
unsupported together with DB fixtures. Nothing is enforced: a fixture cannot see the
consumer's fixture scopes. Instead the async-views example project carries a parity test
that proves loop-per-test still holds for `db` tests, so a rustest scheduler change
becomes a CI failure rather than a consumer's flaky suite.

## Skips

rustest recognises only its own skip exception. rustest-django's fixtures raise
`rustest.skip()`. `unittest.SkipTest` raised inside a test body (Django's
`skipIfDBFeature` and friends) is reported by rustest as a failure; that is a rustest gap
tracked in the upstream-asks decision, not something a fixture can translate.
