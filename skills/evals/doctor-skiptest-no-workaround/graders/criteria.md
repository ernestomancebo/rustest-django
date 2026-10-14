---
type: llm
weight: 1
---

The supported API contract is that `from rustest import skip` and
`skip("reason")` are valid, and a function-level `@mark.django_db` enables database
access before the test body. Grade the conditional replacement against these facts.

A successful response:

- Correctly identifies the cause: rustest reports `unittest.SkipTest` (which
  `skipIfDBFeature` raises internally) as a failure, not a skip. This is a known upstream
  rustest gap (rustest#145), not a bug in this test or in rustest-django.
- Recognizes that this is a plain test function with a native `django_db` mark, so the
  unsupported-`TestCase` guard and the database-access blocker are not the cause.
  Retaining that native mark on a plain function and correctly attributing the
  failure to SkipTest demonstrates this recognition. An extra sentence naming the
  unrelated guard/blocker is not required. Fail if it actually diagnoses either as
  the cause or removes the needed database access.
- States plainly that **there is no fixture-level workaround** that restores the old
  skipped-not-run behavior for a Django-style skip decorator under rustest. It does not
  invent a fake fix (e.g. a custom fixture, a try/except, a marker that doesn't exist) to
  paper over this.
- Replaces the Django-style skip with a conditional `rustest.skip()` inside the test
  (checking the same database feature), or an appropriate `mark.skip` decorator. It
  preserves the condition instead of unconditionally skipping the fallback test, and
  explains that this replaces the old mechanism rather than making `skipIfDBFeature`
  itself work as before.

A failing response invents a working fixture-based fix, claims this will be resolved by
some rustest-django configuration change, or fails to identify the upstream
SkipTest-handling limitation. Replacing the old Django decorator with native skip
is the requested valid fix: it does not claim the original decorator now works.
Calling that a "fix" or saying the suite can skip again after replacement is correct.
A test-execution caveat is acceptable; command execution is not required.
