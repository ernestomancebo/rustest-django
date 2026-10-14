# Unsupported features

The fixture, marker, and configuration ports cover all 31 public fixture names in the
audited pytest-django surface. The remaining boundaries are runner capabilities and
command-line integration, rather than unsupported fixture stubs.

## Unittest-style `TestCase` subclasses

`SimpleTestCase`, `TestCase`, `TransactionTestCase`, and `LiveServerTestCase` subclasses
are unsupported: rustest runs their methods but discards the result, so every method
would otherwise silently report as passed regardless of what happened. An autouse
guard fails these loudly per method. Rewrite as plain test functions using
`db` / `transactional_db` or the `live_server` fixture; see the
[Migration Guide](../migration-guide.md).

## Class and module marks

Rustest 0.18 does not propagate class-level marks or module-level `pytestmark` to test
methods. Apply markers to functions, or use the `rustest_django.django_db` class
decorator for database tests. See [Markers](markers.md#function-vs-class-marks).

## Runner flags

Rustest has no plugin flag-registration interface. Configure Django options using
environment variables and `[tool.rustest-django]` in `pyproject.toml`, with compatible
pytest configuration fallbacks. This includes equivalents for settings selection,
database reuse/recreation, migrations, live-server host/port, template-variable
checking, and configuration-class selection.

Pytest's `addopts` does not become rustest CLI arguments. The
[configuration reference](configuration.md) lists supported keys and overrides.

## Parallel database identity

The database suffix fixtures apply tox and supplied worker identities before test
database creation. Rustest's experimental parallel mode does not expose a supported
automatic identity to this plugin. Separate processes sharing a database server need
distinct `RUSTEST_DJANGO_DB_SUFFIX` values; the suffix port alone does not establish
native parallel-runner database isolation.
