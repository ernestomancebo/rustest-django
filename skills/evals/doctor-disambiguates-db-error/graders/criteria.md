---
type: llm
weight: 1
---

A successful response treats File A and File B as two distinct causes, not one:

- **File A**: `import pytest` / `@pytest.mark.django_db`, but the run command has no
  `--pytest-compat`, so the mark is silently invisible. Fix: add `--pytest-compat` to the
  run command, or rewrite this file's imports to `rustest.mark`.
- **File B**: already uses `rustest.mark` and runs with `--pytest-compat`, but the
  `@mark.django_db` is applied to a *class*, not each method — class-level marks (and
  module-level `pytestmark`) don't propagate to methods in rustest. Fix: use the
  `rustest_django.django_db` class decorator instead of `@mark.django_db` directly on the
  class, or mark `test_create`/`test_cancel` individually.

A failing response gives the same fix for both (e.g. "add --pytest-compat" to both, or
"mark each method" to both), conflates the two causes, or doesn't notice that File B is
already running under `--pytest-compat` and using the right import already.
