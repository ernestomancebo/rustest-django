# Unsupported features

A handful of pytest-django features exist in rustest-django only to fail loudly --
naming exactly what's unsupported, rather than being silently missing or (worse) silently
doing the wrong thing. If your suite doesn't use these, you'll never see them.

## `live_server` fixture

Not implemented in v1. There's no drop-in alternative today; if you need a real live
server for browser-driven tests (Selenium, Playwright), that use case isn't supported yet.

## `django_db_serialized_rollback` fixture

Not implemented in v1. If migration-loaded data is disappearing after a
`transactional_db` test, try `db` instead: it wraps the test in a transaction rather than
truncating tables, so that data survives.

## `django_isolated_apps` fixture

Not implemented in v1. This was a narrow escape hatch in pytest-django for testing custom
`AppConfig`/model definitions in isolation from the real app registry; there's no
rustest-django v1 equivalent.

## `@mark.urls`

Not implemented in v1. Override `settings.ROOT_URLCONF` via the [`settings`
fixture](fixtures.md#settings) instead:

```python
def test_something(settings):
    settings.ROOT_URLCONF = "myapp.test_urls"
    ...
```

## `@mark.ignore_template_errors`

Not implemented in v1. This suppressed Django's strict invalid-template-variable checking
for specific tests; there's no direct rustest-django equivalent.

## Unittest-style `TestCase` subclasses

`SimpleTestCase`, `TestCase`, `TransactionTestCase`, and `LiveServerTestCase` subclasses
are unsupported: rustest runs their methods but discards the result, so every method
would otherwise silently report as passed no matter what actually happened. An autouse
guard fails these loudly per-method instead. Rewrite as plain test functions using the
`db`/`transactional_db` fixtures -- see the [Migration Guide](../migration-guide.md).
