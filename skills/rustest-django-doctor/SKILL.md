---
name: rustest-django-doctor
description: Diagnose a rustest-django test failure or misuse in a Django project — a database-access error, a test that passes when it shouldn't, an unsupported-feature error, or a test that behaves differently under rustest than it did under pytest-django. Use when a rustest-django-backed test suite is failing, flaky, or producing a confusing error, and it's unclear whether the cause is the suite or a known rustest-django limitation.
---

# rustest-django doctor

An advisor for rustest-django-specific failure modes: it tells you which known cause
you've hit and what to do about it, running the suite itself when it can and reasoning
from pasted output when it can't. It does not silently "fix" anything — several of the
causes below have no fix, only a documented reason.

Start with the supplied code and error. Explain only causes matching that evidence;
do not append the rest of the troubleshooting catalogue. When a question explicitly
uses the current feature set, do not add legacy fixture substitutions for a hypothetical
pinned installation. When it explicitly pins an older release, respect that constraint.

## 1. Check for unmigrated TestCase subclasses first

If the supplied failing code is already a plain test function, proceed to its reported
failure. Otherwise, run the detection step from the `rustest-django-migrate-tests`
skill (find `SimpleTestCase`/`TestCase`/`TransactionTestCase`/`LiveServerTestCase`
subclasses in the failing area of the suite). If that skill isn't installed alongside
this one, its detection step is in
[`skills/rustest-django-migrate-tests/SKILL.md`](https://raw.githubusercontent.com/ernestomancebo/rustest-django/main/skills/rustest-django-migrate-tests/SKILL.md) —
fetch it directly rather than reimplementing the search here. If any affected classes
exist, explain the current plugin's guard failure. Without that guard, the runner
discards their method results and can report a false pass. The guard deliberately
rejects these classes; use the migration skill for the rewrite.

**Done when**: the supplied failing test is a plain function, you've confirmed no
unmigrated `TestCase` subclass is in the failing area, or you've identified one and
handed off to `rustest-django-migrate-tests`.

## 2. Run the suite and read the machine-readable output

If you can execute code in this environment: run
`rustest --pytest-compat --llm <path>` (drop `--pytest-compat` only if the target repo
has fully rewritten its imports to `rustest.mark`/etc. — check `conftest.py`'s
`rustest_fixtures` line and whether test files still `import pytest`). This emits one
JSON object per test outcome plus a summary line — read that JSONL instead of scraping
terminal output.

If you can't execute (sandboxed environment, no test database configured, or the human
already has output from a run that happened elsewhere): work from whatever error text
they give you against the same signatures below.

**Done when**: you have either fresh JSONL output or pasted error text to classify
against section 3.

## 3. Classify against known causes

Match the failure to one of these before guessing. Two of them produce the *identical*
symptom for *opposite* reasons — check which applies before recommending a fix:

- **No database permission requested**: an ordinary test can also produce
  `Database access not allowed...` when it requests neither a database fixture nor
  a recognized database marker. The message alone does not prove an import-mode or
  class-marker problem; inspect the test's fixture requests, marks, and runner command.
- **Missing `--pytest-compat`**: a test file still says `import pytest` /
  `@pytest.mark.django_db`, but the run didn't pass `--pytest-compat`. The mark is
  silently invisible, and the test fails with `Database access not allowed, use the
  django_db mark, or the db or transactional_db fixtures to enable it.` — even though the
  mark is right there in the source. Fix: add `--pytest-compat`, or rewrite that file's
  imports to `rustest.mark`.
- **Class-level `@mark.django_db` on a plain class** (not a `TestCase` subclass): the
  *same* `Database access not allowed...` error, but the cause is
  [rustest#143](https://github.com/apex-engineers-inc/rustest/issues/143) — class-level
  marks and module-level `pytestmark` don't propagate to methods at all. Fix: replace the
  class-level `@mark.django_db(...)` with the `rustest_django.django_db` class decorator:

  ```python
  from rustest_django import django_db

  @django_db()
  class TestOrders:
      def test_create(self): ...
  ```

  Call the decorator factory even without options: `@django_db()` or
  `@django_db(transaction=True)`. Alternatively, mark each method individually with
  `@mark.django_db`. The full recipe is in `rustest-django-migrate-tests`'s
  "Class-mark gotcha," step 3 (same file linked above).
- **Unrewritten `pytest_django` import**: `from pytest_django.asserts import ...` raises
  `ImportError`. `--pytest-compat` only shims the `pytest` module, never `pytest_django`.
  Fix: rewrite to `from rustest_django.asserts import ...` (this is exactly
  `rustest-django-migrate-tests`'s step 1, the base migration — same file linked above if
  it's not installed alongside this skill).
- **`unittest.SkipTest` reported as a failure, not a skip**: a test using
  `self.skipTest(...)` or a Django skip decorator (`skipIfDBFeature` and friends) shows up
  as failed rather than skipped. This is
  [rustest#145](https://github.com/apex-engineers-inc/rustest/issues/145) (tracked in
  `docs/spec/upstream.md`, also noted in `docs/spec/async.md`'s "Skips" section), an
  upstream gap with **no workaround possible from a fixture**. Say so plainly — don't
  propose a local fix that doesn't exist; the only real option is
  `rustest.skip()`/`mark.skip` in place of the Django-style skip.
  The failure is the decorator's `SkipTest`, before the test body runs; do not
  attribute it to an assertion in that body.

  Preserve conditional skip semantics across backends. Remove the Django decorator,
  retain the native database mark, and check the same feature inside the test before
  calling native `skip`. Do not offer an unconditional skip for a conditional test,
  even when the current backend makes the condition true. An unconditional
  `mark.skip` is appropriate only for an originally unconditional skip.

  ```python
  from django.db import connection
  from rustest import mark, skip

  @mark.django_db
  def test_json_fallback_path():
      if connection.features.supports_json_field:
          skip("Only for backends without JSON field support")
      raise AssertionError("This path is only for backends without JSON fields")
  ```

  `skip` is a supported public export. When the feature is false, the original test
  body still runs; replacing the skip mechanism must not remove those checks.
- **Flaky/inconsistent DB state on an async test**: a consumer `async def` fixture at
  class, module, or session scope, combined with `db`/`transactional_db`, is an
  unsupported combination (`docs/spec/async.md`'s "Loop scope" section) that runs tests
  concurrently on one loop with nothing enforcing otherwise — it can look exactly like a
  race condition or a flaky test. Check the fixture scopes before chasing a data race; the
  fix is narrowing the loop scope back to function, not adding locking.
- **An old unsupported-feature error naming a fixture or marker**: the current plugin
  implements `live_server`, `django_db_serialized_rollback`, `django_isolated_apps`,
  `@mark.urls`, and `@mark.ignore_template_errors`. Check the installed package,
  interpreter, lockfile, and `rustest_fixtures` registration before applying advice
  from an older release. On the stated current feature set, keep the supported
  fixtures; this is an installation check, not a reason to substitute other fixtures.
- **Migration data missing in a live-server or transactional test**: `live_server`
  activates transactional database access so committed writes reach its HTTP thread.
  Flush teardown can remove migration-created rows. Request
  `django_db_serialized_rollback` alongside `live_server` or `transactional_db`, or
  use `@mark.django_db(transaction=True, serialized_rollback=True)`, to restore the
  database-setup snapshot before the test. The setup machinery creates the snapshot;
  the serialized-rollback fixture requests restoration. `live_server` supplies
  transactional access, not automatic serialized restoration. If the test already
  requests both fixtures, keep both and explain their separate roles.
  Fixture parameter order does not select the isolation mode.
  Replacing the combination with `db` changes commit visibility. Check that migrations
  are enabled when the expected rows are created by data migrations.
- **App-isolation fixture error**: `django_isolated_apps` requires a function-level
  `@mark.django_isolate_apps("django.contrib.contenttypes", ...)` with at least one
  dotted app module path (the importable module, not the app label `"contenttypes"`).
  It returns an isolated registry; it neither creates database tables nor grants DB access.
  Django's original registry is restored after the test, including test or fixture
  setup failures. Class/module marks do not propagate: put the marker on each method
  when grouping these tests in a plain class.
- **Missing template variable under strict checking**: project configuration
  `fail_on_template_vars = true` (or the compatible `FAIL_INVALID_TEMPLATE_VARS`
  setting) rejects missing rendered variables, even with a `default` filter.
  Missing values in conditionals remain allowed. Apply argument-free
  `@mark.ignore_template_errors` to an intentional fallback test; checking resumes
  after that test. Use `@mark.urls("project.test_urls")` for a per-test URLconf;
  both policies apply before consumer fixture setup and restore state after failures.

  The fixture, marker, and configuration contracts are in
  [`site-docs/reference/fixtures.md`](https://github.com/ernestomancebo/rustest-django/blob/main/site-docs/reference/fixtures.md),
  [`markers.md`](https://github.com/ernestomancebo/rustest-django/blob/main/site-docs/reference/markers.md),
  and [`configuration.md`](https://github.com/ernestomancebo/rustest-django/blob/main/site-docs/reference/configuration.md).
- **`rustest --llm` produces no output, or errors on the flag itself**: the target's
  installed rustest predates 0.18.0, where `--llm` shipped (`docs/spec/upstream.md`'s
  "Version target" section). Fix: upgrade rustest, or fall back to reading `--junit-xml`
  output instead of relying on `--llm`.

**Done when**: the failure is matched to exactly one cause above (or confirmed to be none
of them — an ordinary test bug), and the human has been told which it is and why, not
just handed a generic fixture-error explanation.

## Explicitly pinned legacy installations

Use this section only when the request explicitly excludes upgrading an older release
that predates standalone serialized rollback. Do not include it in a current-version
diagnosis or as a hypothetical fallback.

When real commits are unnecessary, `db` preserves migration data through rollback.
`transactional_db` flushes tables and does not restore migration-created rows. If the
test requires real commits, explain that `db` changes that requirement and is not a
valid replacement for the live-server/restoration combination.
