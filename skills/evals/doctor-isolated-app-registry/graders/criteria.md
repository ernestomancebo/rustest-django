---
type: llm
weight: 1
---

PASS when the response imports rustest.mark, applies the function-level
@mark.django_isolate_apps("django.contrib.contenttypes"), preserves the Temporary
model and registry assertion, and requests django_isolated_apps. It explains that
the original registry is restored after the test and fixture failures, that isolation
neither creates tables nor grants DB access, and class/module marks do not propagate.

FAIL if it calls the feature unsupported, uses a marker with no app name or only an
app label instead of an importable app module, replaces the supplied registry with
the global registry, promises automatic tables/DB access, or promises class-mark
propagation. No database fixture is needed for this registry-only test.
