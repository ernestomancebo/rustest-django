---
name: rustest-django-doctor
description: Diagnose a rustest-django test failure or misuse in a Django project — a database-access error, a test that passes when it shouldn't, an unsupported-feature error, or a test that behaves differently under rustest than it did under pytest-django. Use when a rustest-django-backed test suite is failing, flaky, or producing a confusing error, and it's unclear whether the cause is the suite or a known rustest-django limitation.
---

# rustest-django doctor

An advisor for rustest-django-specific failure modes: it tells you which known cause
you've hit and what to do about it, running the suite itself when it can and reasoning
from pasted output when it can't. It does not silently "fix" anything — several of the
causes below have no fix, only a documented reason.

## 1. Check for unmigrated TestCase subclasses first

Before anything else, run the detection step from the `rustest-django-migrate-tests`
skill (find `SimpleTestCase`/`TestCase`/`TransactionTestCase`/`LiveServerTestCase`
subclasses in the failing area of the suite). If that skill isn't installed alongside
this one, its detection step is in
[`skills/rustest-django-migrate-tests/SKILL.md`](https://raw.githubusercontent.com/ernestomancebo/rustest-django/main/skills/rustest-django-migrate-tests/SKILL.md) —
fetch it directly rather than reimplementing the search here. If any affected classes
exist, that's the diagnosis: their methods run but their results are discarded, so a
"passing" or "failing" report from them is not trustworthy either way. Point at that
skill for the fix; don't re-derive the detection logic here.

**Done when**: you've confirmed no unmigrated `TestCase` subclass is in the failing
area, or you've identified one and handed off to `rustest-django-migrate-tests`.

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
  class-level `@mark.django_db(...)` with the `rustest_django.django_db` class decorator
  (full recipe in `rustest-django-migrate-tests`'s "Class-mark gotcha," step 2 — same file
  linked above if it's not installed alongside this skill), or mark each method
  individually.
- **Unrewritten `pytest_django` import**: `from pytest_django.asserts import ...` raises
  `ImportError`. `--pytest-compat` only shims the `pytest` module, never `pytest_django`.
  Fix: rewrite to `from rustest_django.asserts import ...`.
- **`unittest.SkipTest` reported as a failure, not a skip**: a test using
  `self.skipTest(...)` or a Django skip decorator (`skipIfDBFeature` and friends) shows up
  as failed rather than skipped. This is
  [rustest#145](https://github.com/apex-engineers-inc/rustest/issues/145) (tracked in
  `docs/spec/upstream.md`, also noted in `docs/spec/async.md`'s "Skips" section), an
  upstream gap with **no workaround possible from a fixture**. Say so plainly — don't
  propose a local fix that doesn't exist; the only real option is
  `rustest.skip()`/`mark.skip` in place of the Django-style skip.
- **Flaky/inconsistent DB state on an async test**: a consumer `async def` fixture at
  class, module, or session scope, combined with `db`/`transactional_db`, is an
  unsupported combination (`docs/spec/async.md`'s "Loop scope" section) that runs tests
  concurrently on one loop with nothing enforcing otherwise — it can look exactly like a
  race condition or a flaky test. Check the fixture scopes before chasing a data race; the
  fix is narrowing the loop scope back to function, not adding locking.
- **An unsupported-feature error naming a fixture or marker** (`live_server`,
  `django_db_serialized_rollback`, `django_isolated_apps`, `@mark.urls`,
  `@mark.ignore_template_errors`) — not a bug, a documented v1 gap; full list and
  rationale in
  [`site-docs/reference/unsupported.md`](https://raw.githubusercontent.com/ernestomancebo/rustest-django/main/site-docs/reference/unsupported.md).
  Point at the alternative if one exists (e.g. `transactional_db` in place of a vanished
  `django_db_serialized_rollback`-loaded fixture); say plainly if there isn't one yet
  (`live_server` has none).
- **`rustest --llm` produces no output, or errors on the flag itself**: the target's
  installed rustest predates 0.18.0, where `--llm` shipped (`docs/spec/upstream.md`'s
  "Version target" section). Fix: upgrade rustest, or fall back to reading `--junit-xml`
  output instead of relying on `--llm`.

**Done when**: the failure is matched to exactly one cause above (or confirmed to be none
of them — an ordinary test bug), and the human has been told which it is and why, not
just handed a generic fixture-error explanation.
