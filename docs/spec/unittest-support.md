# Unittest-style Django TestCase support

Spec section for rustest-django v1. Decided in wayfinder ticket #12.

## Decision

Out for v1. A pytest-django suite that subclasses `django.test.SimpleTestCase`
(`TestCase`, `TransactionTestCase`, `LiveServerTestCase`) is not supported: rustest
collects and runs the methods, but discards the result, so every method reports as passed
regardless of outcome ([research
#5](https://github.com/ernestomancebo/rustest-django/issues/5)). No `setUpClass`, no
fixture injection, no marks reach these classes either. `--pytest-compat` changes
nothing.

Plain `unittest.TestCase` (not a Django subclass) is rustest's concern, not
rustest-django's, and is unaffected by this decision.

## Failure behaviour

A per-method autouse guard detects a `SimpleTestCase` subclass and fails every method
loudly, with a message naming the class and stating unittest-style tests are unsupported
in v1. No opt-out.

## Why not silently skip

A silently-skipped test with a discarded result looks identical to a passing one in CI
output. Failing loudly is the only outcome that doesn't let a consumer believe a migrated
suite has parity when it was never actually run.

The implemented message uses the `rustest-django: ` prefix, names the affected class,
and recommends plain functions with `db` / `transactional_db`. See the
[error-message design](../plans/2026-09-16-error-messages-design.md).
