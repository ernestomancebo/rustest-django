---
type: llm
weight: 1
---

A successful response:

- Correctly identifies the cause: rustest reports `unittest.SkipTest` (which
  `skipIfDBFeature` raises internally) as a failure, not a skip. This is a known upstream
  rustest gap (rustest#145), not a bug in this test or in rustest-django.
- Recognizes that this is a plain test function with a native `django_db` mark, so the
  unsupported-`TestCase` guard and the database-access blocker are not the cause.
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
some rustest-django configuration change, or fails to mention that this is a known,
unworkaroundable upstream limitation.
