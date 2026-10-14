---
status: accepted
---

# DB isolation reuses Django TestCase internals

Per-test isolation is built the way pytest-django builds it: a throwaway `TestCase` or
`TransactionTestCase` subclass per test, driven by hand through `setUpClass`, `_pre_setup`,
`_post_teardown`, `tearDownClass`, with `TestCase.setUpClass`/`tearDownClass` deliberately
bypassed so no class-level atomics run and no connections are closed. We chose this over
a direct `transaction.atomic()` + `flush` implementation because the parity contract with
pytest-django only holds if edge cases (multi-database, `serialized_rollback`,
`reset_sequences`, `available_apps`, on-commit capture) behave exactly as Django's, and the
spike (wayfinder ticket #8) proved the pattern runs unchanged under rustest.

## Consequences

- Couples to private Django API. Every private touch goes through one internal
  `django_compat` module; supported Django range (4.2 LTS, 5.x, 6.x) is pinned in package
  metadata and exercised by the CI matrix.
- Marker kwargs (`transaction`, `reset_sequences`, `databases`, `serialized_rollback`,
  `available_apps`) pass straight through to class attributes with pytest-django's
  defaults; `reset_sequences=True` forces flush mode.
- rustest has no `request.fixturenames`. The `rustest_compat` adapter infers the fixture
  closure from public node metadata, the public fixture registry, and autouse decorator
  metadata before building isolation. Flag fixtures also record dynamic requests.
  Repeated requests for an established mode are idempotent; a late request requiring a
  stronger mode raises rather than rebuilding isolation and discarding setup data.
- Live-server tests receive transactional access, including through session-scoped
  browser fixtures. The server belongs to the session; allowed-host overrides and
  database isolation belong to each test.
- Test databases are created lazily on the first DB test, for every alias in
  `settings.DATABASES`, and every alias is serialized, matching `manage.py test`.
- Isolation fixtures wrap `yield` in `try/finally` and re-raise teardown errors, because
  rustest skips post-`yield` code when a sibling fixture fails setup.
