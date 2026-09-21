---
name: rustest-django-migrate-tests
description: Migrate a Django TestCase-based test suite (SimpleTestCase, TestCase, TransactionTestCase, LiveServerTestCase subclasses) to rustest-django's plain-function style. Use when porting a Django/pytest-django project to rustest-django, when a repo already using rustest-django still has unittest-style Django test classes, or when rustest-django reports its unittest-style guard failure ("unittest-style tests are unsupported").
---

# Migrate TestCase to rustest-django

rustest runs a `unittest.TestCase` method but discards its `TestResult`, so a failing
assertion inside one would otherwise be silently reported as passed. rustest-django
guards against that by failing every method of a Django `TestCase` family class loudly,
with no opt-out — the decision and its rationale are in
[`docs/spec/unittest-support.md`](https://github.com/ernestomancebo/rustest-django/blob/main/docs/spec/unittest-support.md).
There is no way to make these classes work as-is: the fix is rewriting them as plain test
functions.

Before starting: if the target repo hasn't done the base migration yet (swapped
`pytest_django` for `rustest_django` in `conftest.py`, decided `--pytest-compat` vs.
rewritten imports), do that first per
[`migration-guide.md`](https://raw.githubusercontent.com/ernestomancebo/rustest-django/main/site-docs/migration-guide.md).
This skill only covers the `TestCase`-family rewrite, not the base name-swap.

## 1. Find every affected class

Search the target repo's test files for classes subclassing `django.test.SimpleTestCase`,
`TestCase`, `TransactionTestCase`, or `LiveServerTestCase` (directly, or via a project's
own mixin that subclasses one of them). `unittest.TestCase` on its own, with no Django
subclass in its bases, is not affected — leave those alone.

**Done when**: you have the full list of affected classes and their methods, ready to
tell the human "N classes, M methods" before touching anything. Report the list before
rewriting if the count is large enough that a wrong scope call would be expensive to
undo.

## 2. Rewrite class attributes to marker kwargs

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

## 3. Rewrite the test bodies

- `self.assertX(...)` → import the same name as a module-level function from
  `rustest_django.asserts` (`from rustest_django.asserts import assertContains`) and call
  it positionally (`assertContains(response, "x")`), dropping `self`.
- `self.client` / `self.async_client` / `self.request_factory` → `client` / `async_client`
  / `rf` fixture parameters on the test function.
- `self.settings(...)` context manager, or a class-level `@override_settings(...)` →
  the `settings` fixture.
- `self.assertNumQueries(...)` → the `django_assert_num_queries` fixture (context
  manager/decorator), not a method call.
- `setUp`/`tearDown` bodies → inline at the top/bottom of each rewritten function, or
  pulled into a project-local fixture if genuinely shared across many tests.

**Done when**: every method of the class compiles as a standalone function using only
fixtures and module-level asserts — no remaining reference to `self`.

## 4. Flag the gaps — do not silently "handle" these

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
