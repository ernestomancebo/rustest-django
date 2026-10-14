---
name: rustest-django-migrate-tests
description: Migrate a Django/pytest-django test suite to rustest-django — the base pytest_django-to-rustest_django module re-referencing, and the TestCase-family rewrite (SimpleTestCase, TestCase, TransactionTestCase, LiveServerTestCase subclasses) where present. Use when porting a Django/pytest-django project to rustest-django, when a repo already using rustest-django still has unittest-style Django test classes, or when rustest-django reports its unittest-style guard failure ("unittest-style tests are unsupported").
---

# Migrate a pytest-django suite to rustest-django

rustest runs a `unittest.TestCase` method but discards its `TestResult`, so a failing
assertion inside one would otherwise be silently reported as passed. rustest-django
guards against that by failing every method of a Django `TestCase` family class loudly,
with no opt-out — the decision and its rationale are in
[`docs/spec/unittest-support.md`](https://github.com/ernestomancebo/rustest-django/blob/main/docs/spec/unittest-support.md).
There is no way to make these classes work as-is: the fix is rewriting them as plain test
functions.

## 1. Do the base pytest-django migration first (skip if already done)

Get the target repo running under rustest-django at all, before touching any
`TestCase`-family class: swap `pytest_plugins = ["pytest_django"]` for
`rustest_fixtures = ["rustest_django"]` in `conftest.py`, and decide per file whether to
keep `import pytest` (running with `--pytest-compat`) or rewrite to
`from rustest import mark`. Either way, rewrite `pytest_django`'s own imports
unconditionally (`from pytest_django.asserts import ...` →
`from rustest_django.asserts import ...`) — `--pytest-compat` only shims the `pytest`
module, never `pytest_django`. Full worked example and rationale in
[`migration-guide.md`](https://raw.githubusercontent.com/ernestomancebo/rustest-django/main/site-docs/migration-guide.md).

**Done when**: `conftest.py` is updated, every test file's import style is a deliberate
choice rather than an accident of what was already there, and no file still imports
directly from `pytest_django`.

## 2. Find every affected class

Search the target repo's test files for classes subclassing `django.test.SimpleTestCase`,
`TestCase`, `TransactionTestCase`, or `LiveServerTestCase` (directly, or via a project's
own mixin that subclasses one of them). `unittest.TestCase` on its own, with no Django
subclass in its bases, is not affected — leave those alone.

**Done when**: you have the full list of affected classes and their methods. Report it to
the human as "N classes, M methods" before touching anything, regardless of how small
that count is — visibility into scope is the point, not just a safety valve for large
migrations.

## 3. Rewrite class attributes to marker kwargs

Django `TestCase` class attributes map straight onto `@mark.django_db(...)` (from
`rustest.mark`, or `pytest.mark` under `--pytest-compat`; full kwarg reference in
[`site-docs/reference/markers.md`](https://github.com/ernestomancebo/rustest-django/blob/main/site-docs/reference/markers.md)):

| Class attribute / shape | Marker kwarg |
|---|---|
| Subclasses `TransactionTestCase` (non-atomic) | `transaction=True` |
| `databases = {...}` | `databases=[...]` |
| `reset_sequences = True` | `reset_sequences=True` |
| `serialized_rollback = True` | `serialized_rollback=True` (only meaningful with `transaction=True`) |

Applying the marker to a function is equivalent to requesting the `db` fixture (or
`transactional_db`, etc.) directly — don't do both.

**Class-mark gotcha**: `@mark.django_db(...)` on a *class* does not propagate to its
methods (upstream [rustest#143](https://github.com/apex-engineers-inc/rustest/issues/143),
tracked in
[`docs/spec/upstream.md`](https://github.com/ernestomancebo/rustest-django/blob/main/docs/spec/upstream.md);
same is true of module-level `pytestmark`). If you're grouping the rewritten methods back
into a plain class instead of top-level functions, use the `rustest_django.django_db`
class decorator instead — it applies the marker to every `test*` method at
class-decoration time:

```python
from rustest_django import django_db

@django_db(transaction=True)
class TestSomething:
    def test_one(self): ...
```

The class decorator is a factory: always call it, using `@django_db()` when there
are no options and `@django_db(transaction=True)` when passing options.

## 4. Rewrite the test bodies

- Django-specific assertions with documented module-level equivalents, such as
  `self.assertContains(...)` and `self.assertNotContains(...)` → import the helper from
  `rustest_django.asserts` and drop `self`: `assertContains(response, "x")`. These two
  helpers are confirmed public exports, so use their documented signatures directly.
  For other assertion names, check the package exports when source is available and
  flag unconfirmed mappings separately; continue the documented conversions above.
- Inherited unittest assertions → Python assertions: `self.assertEqual(a, b)` becomes
  `assert a == b`, `self.assertTrue(value)` becomes `assert value`, and
  `self.assertFalse(value)` becomes `assert not value`. Preserve any custom failure
  message. These inherited methods are not exported by `rustest_django.asserts`.
- `with self.assertRaises(Error): ...` → `with raises(Error): ...`, importing `raises`
  from `rustest`; this is a confirmed public export. Retain callable-style checks by
  moving the call inside the context. `with self.assertRaisesRegex(Error, pattern)`
  becomes `with raises(Error, match=pattern)`.
- `self.client` / `self.async_client` / `self.request_factory` → `client` / `async_client`
  / `rf` fixture parameters on the test function.
- `self.settings(...)` context manager, or a class-level `@override_settings(...)` →
  the `settings` fixture.
- `self.assertNumQueries(...)` → the `django_assert_num_queries` fixture (context
  manager/decorator), not a method call.
- `setUp`/`tearDown` bodies → inline at the top/bottom of each rewritten function, or
  pulled into a project-local fixture if genuinely shared across many tests.

**Done when**: every method of the class compiles as a standalone function using only
fixtures and module-level asserts — no remaining reference to `self`. When asked for
a runnable rewrite, supply the whole test file with imports and every original check.
Use the confirmed exports above even when the sandbox cannot inspect installed source;
state that execution was unavailable separately from the supported conversion.

## Per-test features and project defaults

- Rewrite `LiveServerTestCase` methods to functions requesting `live_server`.
  `str(live_server)`, `live_server.url`, and `live_server + "/path/"` give its address.
  The session server starts lazily; each consuming test gets transactional DB access.
  Request `django_db_serialized_rollback` as well when data migrations populate rows
  that must survive earlier transactional flushes. Avoid adding `db` for a server test
  that needs committed writes visible to the HTTP thread.
- Keep function-level `@mark.urls("project.test_urls")` for per-test routes and
  `@mark.django_isolate_apps("app.module")` with `django_isolated_apps` for an isolated
  registry. Registry isolation does not create tables or enable database access.
- Keep strict template checking as a project setting and use argument-free
  `@mark.ignore_template_errors` only on intentional missing-variable fallback tests.
  These marker contexts cover consumer fixture setup and restore after failures.
- Put project defaults in `[tool.rustest-django]`: `settings_module`, `configuration`,
  `live_server_host`, `live_server_port`, and `fail_on_template_vars`. Port `0` asks
  the OS for a free port. Native boolean keys use actual TOML booleans. Optional
  django-configurations support is installed with `rustest-django[configurations]`.
  Environment overrides win over native TOML, then the selected pytest INI/TOML
  fallback. Discovery uses the nearest supported directory, even an empty supported
  source; within it pytest.ini, .pytest.ini, tool.pytest, then tool.pytest.ini_options
  select one fallback. Unrelated pyproject files are skipped.
  See the [configuration reference](https://github.com/ernestomancebo/rustest-django/blob/main/site-docs/reference/configuration.md)
  for accepted keys. Pytest `addopts` and plugin CLI flags are not forwarded;
  use `reuse_db = true` / `RUSTEST_DJANGO_REUSE_DB=true` for `--reuse-db`, and
  `migrations = false` / `RUSTEST_DJANGO_MIGRATIONS=false` for `--nomigrations`.
  `RUSTEST_DJANGO_CREATE_DB=true` forces recreation; this override is environment-only.
  Per-process DB suffixes require external identities: `TOX_PARALLEL_ENV` adds the tox
  suffix, then `RUSTEST_DJANGO_DB_SUFFIX` adds a worker suffix (falling back to
  `PYTEST_XDIST_WORKER`). Both suffixes can apply together; they are not competing
  fallback sources. Rustest worker IDs are not supplied automatically, and in-memory
  SQLite/mirrors are excluded from suffixing.

## 5. Flag the gaps — do not silently "handle" these

These `TestCase` features have no confirmed rustest-django equivalent. Don't invent one;
tell the human what you found and let them decide:

- **`setUpClass` / `setUpTestData`** — class-scoped setup. No rustest fixture scope maps
  onto this cleanly; check whether the data can just move into each test function, or
  needs a genuinely shared fixture the human should design.
- **`addCleanup`** — no direct equivalent; falls back to a fixture's own `yield`-then-cleanup
  teardown, or plain code at the end of the test function.
- **`subTest`** — no sub-test reporting in rustest; the usual replacement is parametrizing
  the test function instead of looping inside it.
- **`fixtures = [...]`** (Django JSON/YAML fixture loading) — no rustest-django loader;
  call `django.core.management.call_command("loaddata", ...)` explicitly inside the test
  or a fixture.
- **`self.skipTest(...)` / `unittest.SkipTest`** (including Django's `skipIfDBFeature` and
  friends) — rustest reports this as a **failure**, not a skip
  ([rustest#145](https://github.com/apex-engineers-inc/rustest/issues/145), also noted in
  [`docs/spec/async.md`](https://github.com/ernestomancebo/rustest-django/blob/main/docs/spec/async.md)),
  with no workaround possible from a fixture. Replace with `rustest.skip()` / `mark.skip`
  directly; don't leave the old skip call in place expecting it to behave.

**Done when**: every gap actually present in the class under rewrite has been called out
by name to the human, even if the rewrite is otherwise complete.
