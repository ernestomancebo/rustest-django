# Upstream relationship

Spec section for rustest-django v1. Decided in wayfinder ticket #16.

## Version target

v1 targets rustest 0.18.0, the published release everything in this spec was researched
and prototyped against. Package metadata pins `rustest>=0.18,<1.0`. Adopting a released
rustest 1.0 requires a separate compatibility spike and parity run before changing the
dependency range; development branches are not build dependencies for this spec.

## Gaps reported upstream

| gap | rustest issue | rustest-django response |
|---|---|---|
| `unittest.TestCase` outcomes discarded | already tracked as [rustest#129](https://github.com/Apex-Engineers-Inc/rustest/issues/129); we added a comment with the Django-specific case | unsupported, fails loudly (#12) |
| Class-level `@mark.django_db` / module `pytestmark` not propagated to methods | [rustest#143](https://github.com/Apex-Engineers-Inc/rustest/issues/143) | workaround shipped: `rustest_django.django_db` class decorator (below) |
| `request.fixturenames` / `request.addfinalizer` absent | [rustest#144](https://github.com/Apex-Engineers-Inc/rustest/issues/144) | worked around internally: per-test context flags (#9) replace `fixturenames`; `addfinalizer` is unused, everything uses yield-fixture teardown |
| `unittest.SkipTest` reported as failed, not skipped | [rustest#145](https://github.com/Apex-Engineers-Inc/rustest/issues/145) | no workaround possible from a fixture; documented limitation |
| Two doc inaccuracies (`pytest_asyncio.fixture` claimed unsupported; stale async-fixture warning under `--pytest-compat`) | [rustest#146](https://github.com/Apex-Engineers-Inc/rustest/issues/146) | none needed |

If any of these land upstream, the corresponding rustest-django workaround becomes
redundant and is removed in a follow-up, not silently kept.

## `rustest_django.django_db` class decorator

Ships in v1 alongside the `@mark.django_db(...)` marker. Applies the identical marker to
every `test*` method on the decorated class at class-decoration time, the same technique
rustest's own `mark.asyncio` uses for class propagation. Lets a pytest-django suite that
puts `@pytest.mark.django_db` on a plain `Test*` class (not `unittest.TestCase`) work
without waiting on rustest#143.

```python
@rustest_django.django_db(transaction=True)
class TestFoo:
    def test_a(self): ...
    def test_b(self): ...
```

Equivalent to decorating each method individually with `@mark.django_db(transaction=True)`.
Not offered as a function decorator; use `@mark.django_db(...)` directly there.

## Listing on rustest's pytest-plugins page

The release prerequisite is satisfied by
[rustest-django 0.0.2](https://pypi.org/project/rustest-django/0.0.2/).
The remaining work is an upstream documentation contribution, tracked in
[#26](https://github.com/ernestomancebo/rustest-django/issues/26).

## Fixture setup ordering adapter

Rustest 0.18 resolves named test fixtures before autouse fixtures. The plugin uses a
small `marker_activation` adapter at Python's source-module loading boundary to make
its combined Django context the first runner-managed test dependency. App, URL,
template, and database policies therefore apply during consumer fixture setup as well
as the test body, and teardown stays in the runner's fixture lifecycle.

Activation is limited to a public rustest run and directories beneath a conftest that
declares the Django fixture module. Ordinary pytest runs, helper-only imports, and
plain sibling test suites retain their behavior. Test metadata, signatures, defaults,
and ordinary direct calls are preserved. This adapter and `rustest_compat` fixture
discovery are the places to revisit when upstream exposes an early setup hook and
fixture-closure metadata.
