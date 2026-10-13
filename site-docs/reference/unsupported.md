# Unsupported features

The supported tier covers pytest-django's core fixtures and selected additional
features. The remaining port gaps are listed below. Requesting an unsupported fixture
or applying a guarded marker to a function raises a `rustest-django: ...` error. The
`django_isolate_apps` marker is currently unhandled, as described below.

## Remaining port inventory

| Surface | Current status |
|---|---|
| `live_server` fixture and `--liveserver` configuration | The fixture raises an unsupported error; server startup, teardown, and configuration are not implemented. Tracked in [#25](https://github.com/ernestomancebo/rustest-django/issues/25). |
| `django_db_serialized_rollback` fixture | Raises an unsupported error. The `django_db` marker's `serialized_rollback` kwarg is supported. |
| `django_isolated_apps` fixture and `django_isolate_apps` marker | The fixture raises an unsupported error; the marker alone is ignored and does not isolate model registration. |
| `urls` marker | Raises an unsupported error on a test function; override `settings.ROOT_URLCONF` instead. |
| `ignore_template_errors` marker and `--fail-on-template-vars` option | The marker raises an unsupported error on a test function; template-variable failure instrumentation is not implemented. |
| django-configurations (`--dc`, `DJANGO_CONFIGURATION`) | No integration with its settings importer. |
| Parallel/tox/xdist database suffix fixtures | The names exist, but the implementations do not add database-name suffixes. |

`live_server` has an implementation issue. The other excluded features need a scope
decision before adding them; they are not scheduled v1 work. Core options such as
`--reuse-db`, `--create-db`, `--ds`, and migration selection already have
[environment/configuration equivalents](configuration.md).

## `live_server` fixture

Not implemented in v1. There's no drop-in alternative today; if you need a real live
server for browser-driven tests (Selenium, Playwright), that use case isn't supported yet.

## `django_db_serialized_rollback` fixture

Not implemented in v1. If migration-loaded data is disappearing after a
`transactional_db` test, try `db` instead: it wraps the test in a transaction rather than
truncating tables, so that data survives.

When real transactions are needed, the supported
[`django_db` marker](markers.md) accepts `transaction=True, serialized_rollback=True`.
This marker support does not implement the standalone fixture.

## `django_isolated_apps` fixture

Not implemented in v1. This was a narrow escape hatch in pytest-django for testing custom
`AppConfig`/model definitions in isolation from the real app registry; there's no
rustest-django v1 equivalent.

## `@mark.django_isolate_apps`

Not implemented or guarded in v1. Applying the marker alone does not isolate model
registration: newly defined models still use the normal app registry. Requesting the
companion `django_isolated_apps` fixture fails with the unsupported-feature error.

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

## Runner options and database suffixes

`--fail-on-template-vars`, live-server address selection (`--liveserver`), and
django-configurations selection (`--dc` / `DJANGO_CONFIGURATION`) have no v1 equivalent.
The [configuration reference](configuration.md) lists the supported settings.

The `django_db_modify_db_settings_parallel_suffix`, `django_db_modify_db_settings_tox_suffix`,
and `django_db_modify_db_settings_xdist_suffix` fixtures are defined for compatibility
with consumer overrides, but they are no-ops. They provide no per-worker or per-tox-env
database naming.

## Marker argument limitations

Use the documented keyword arguments for [`django_db`](markers.md). Positional values
are ignored in v1, and misspelled or unknown kwargs are also ignored rather than
rejected. These are compatibility gaps that require a code follow-up, separate from
the excluded fixtures above. Class and module mark propagation is covered in the
[marker reference](markers.md).

The [configuration reference](configuration.md#boolean-values) also records a validation
gap: TOML boolean keys use truthiness rather than rejecting wrong types.

## Unittest-style `TestCase` subclasses

`SimpleTestCase`, `TestCase`, `TransactionTestCase`, and `LiveServerTestCase` subclasses
are unsupported: rustest runs their methods but discards the result, so every method
would otherwise silently report as passed no matter what actually happened. An autouse
guard fails these loudly per-method instead. Rewrite as plain test functions using the
`db`/`transactional_db` fixtures -- see the [Migration Guide](../migration-guide.md).
