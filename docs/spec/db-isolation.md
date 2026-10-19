# DB isolation machinery

Spec section for rustest-django v1. Decided in wayfinder ticket #9. Full rationale in
[ADR 0001](../adr/0001-db-isolation-on-django-testcase-internals.md).

## Approach

Reuses Django's own `TestCase`/`TransactionTestCase` internals rather than a direct
`transaction.atomic()` + flush implementation: a throwaway subclass per test, driven by
hand through `_pre_setup`/`_post_teardown`, with `setUpClass`/`tearDownClass` deliberately
bypassed so no class-level atomics run and no connections close. This is what
pytest-django itself does, and it's the only way the edge cases (multi-database,
`serialized_rollback`, `reset_sequences`, `available_apps`, on-commit capture) behave
exactly like Django's.

## DB blocker

Installed for the whole session: any database access with no isolation active raises.
Lifted only by an isolation (below) or an explicit unblock (`django_db_blocker`).

## Isolation modes

Requested by database fixtures, `live_server`, or `@mark.django_db(...)`:

- **Rollback** (default): wraps the test in a transaction, rolled back after.
- **Flush**: tables emptied after the test. Used when `transaction=True`, or forced by
  `reset_sequences=True` or live-server access.

Marker kwargs (`transaction`, `reset_sequences`, `databases`, `serialized_rollback`,
`available_apps`) pass straight through to Django's TestCase class attributes,
pytest-django's defaults and validation.

## Fixture-requested upgrades

The `rustest_compat` adapter infers the fixture closure before isolation is built,
including dependent fixtures, autouse fixtures, and `usefixtures` marks. Direct
parametrized values are excluded; consumer overrides retain their own behavior. This lets live-server and
serialized-rollback requirements combine with other database fixtures regardless of
parameter order. Flag fixtures also record dynamic requests. Repeating an already
established request is idempotent; requesting a stronger mode after isolation has been
built raises instead of rebuilding isolation and losing fixture-created data.

## Test database lifecycle

Test databases are created lazily, on the first DB test, one per alias in
`settings.DATABASES`, every alias serialized — matching `manage.py test`. Owned by
`django_db_setup`.

## Private API isolation

Every touch of Django's private API goes through one internal `django_compat` module.
Supported Django range (4.2 LTS, 5.x, 6.x) is pinned in package metadata and exercised by
the CI matrix (see [testing-and-ci.md](./testing-and-ci.md#ci-matrix)).

## Teardown ordering

Isolation fixtures wrap `yield` in `try`/`finally` and re-raise teardown errors: rustest
skips post-`yield` fixture code when a sibling fixture's setup fails (per
[fixture-lifecycle research](https://github.com/ernestomancebo/rustest-django/issues/4)),
so relying on plain post-yield cleanup would leak a database in that case.
