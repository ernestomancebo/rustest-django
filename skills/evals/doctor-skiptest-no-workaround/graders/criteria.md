---
type: llm
weight: 1
---

A successful response:

- Correctly identifies the cause: rustest reports `unittest.SkipTest` (which
  `skipIfDBFeature` raises internally) as a failure, not a skip. This is a known upstream
  rustest gap (rustest#145), not a bug in this test or in rustest-django.
- States plainly that **there is no fixture-level workaround** that restores the old
  skipped-not-run behavior for a Django-style skip decorator under rustest. It does not
  invent a fake fix (e.g. a custom fixture, a try/except, a marker that doesn't exist) to
  paper over this.
- The only thing it may correctly suggest changing is replacing the Django-style skip
  with `rustest.skip()` / `mark.skip` directly in the test body — and even then, it's
  honest that this is a different mechanism (an explicit skip call) rather than a true
  fix for `skipIfDBFeature` itself continuing to work as before.

A failing response invents a working fixture-based fix, claims this will be resolved by
some rustest-django configuration change, or fails to mention that this is a known,
unworkaroundable upstream limitation.
