# Public API

Spec section for rustest-django v1. Decided in wayfinder ticket #13. Every name below is
pytest-django's name; the port changes internals, never the surface.

## Name swap

A consumer migrates by:

1. Replacing `pytest_plugins = ["pytest_django"]` (or the implicit `pytest11` entry point)
   with `rustest_fixtures = ["rustest_django"]` in `conftest.py`.
2. Either keeping `import pytest` in tests and running `rustest --pytest-compat`, or
   rewriting those imports to `from rustest import fixture, mark, raises, ...`. Both are
   supported; without the flag, real pytest marks are invisible to rustest fixtures.
3. Replacing `from pytest_django...` imports with `from rustest_django...`.

## Markers

`@mark.django_db(transaction=False, reset_sequences=False, databases=None,
serialized_rollback=False, available_apps=None)`, from `rustest.mark` (identical object
as `pytest.mark` under `--pytest-compat`). Arguments bind to this signature with
pytest-django's defaults: positional values are accepted in declaration order,
and unknown keywords, duplicate arguments, or excess positional values raise an
error with the `rustest-django: ` prefix. Binding validates the argument signature;
it does not add stricter value-type checks than pytest-django.

`@mark.urls(urls)` accepts a URLconf module name or imported module, including the
keyword spelling. Its per-test context overrides `ROOT_URLCONF`, clears resolver
caches and resets the current URLconf on entry and exit. Django settings and URL
resolution are restored on test or fixture failure.

`@mark.django_isolate_apps(*app_labels)` requires one or more app module strings
and uses Django's `isolate_apps` context for the test. The `django_isolated_apps`
fixture returns the isolated registry, or raises an actionable error when used
without this marker. Registration isolation does not create tables or request
database access.

`@mark.ignore_template_errors` (also callable without arguments) exempts a test
from the project's `fail_on_template_vars` policy. The policy rejects undefined
rendered variables, including filtered expressions, across configured Django
template backends; Django's missing-variable behavior in conditionals is retained.
Failures identify the variable and template origin when available. Backend
`string_if_invalid` values are restored even after test or fixture failures. The
marker does not enable strict checking and rejects arguments.

Function-level marks work directly under rustest 0.18. Class-level marks do not
propagate to methods (rustest limitation, reported upstream as
[rustest#143](https://github.com/Apex-Engineers-Inc/rustest/issues/143)); use the
`rustest_django.django_db(...)` class decorator instead, which applies the marker to
every `test*` method at class-decoration time. See `docs/spec/upstream.md`. Module-level
`pytestmark` has no equivalent in v1.

## Fixtures

Database and lifecycle:
`db`, `transactional_db`, `django_db_reset_sequences`,
`django_db_serialized_rollback`, `django_db_setup`,
`django_db_blocker`, `django_db_createdb`, `django_db_keepdb`, `django_db_use_migrations`,
`django_db_modify_db_settings`, `django_db_modify_db_settings_parallel_suffix`,
`django_db_modify_db_settings_tox_suffix`, `django_db_modify_db_settings_xdist_suffix`,
`django_test_environment`, `live_server`.

`django_db_serialized_rollback` requests snapshot restoration and composes with
transactional database fixtures. `live_server` exposes a real HTTP server through
its `.url` property and string representation, starts it after transactional
database setup, and stops it at session teardown. Tests requesting it receive
transactional isolation so the server thread can see committed data.

The database-settings fixture chain applies `TOX_PARALLEL_ENV` and then
`RUSTEST_DJANGO_DB_SUFFIX` (or `PYTEST_XDIST_WORKER`) to test database names. Mirrors
and in-memory SQLite databases are excluded. This does not provide automatic
database isolation for native rustest parallel workers without a worker suffix.

Clients and users:
`client`, `async_client`, `rf`, `async_rf`, `admin_client`, `admin_user`,
`django_user_model`, `django_username_field`.

Settings, mail, queries:
`settings`, `django_isolated_apps`, `mailoutbox`, `django_mail_patch_dns`,
`django_mail_dnsname`,
`django_capture_on_commit_callbacks`, `django_assert_num_queries`,
`django_assert_max_num_queries`.

Autouse internals, private names, not part of the contract: marker activation,
template policy, mailbox autoclear, and the unittest-style guard.

All session fixtures above are overridable by name from a consumer `conftest.py`.

The fixture-name inventory was compared on 2026-10-13 with pytest-django
[`fixtures.py`](https://github.com/pytest-dev/pytest-django/blob/ad5867df0bbb8ba4743694fbf5489a6b58c00a07/pytest_django/fixtures.py)
and [`plugin.py`](https://github.com/pytest-dev/pytest-django/blob/ad5867df0bbb8ba4743694fbf5489a6b58c00a07/pytest_django/plugin.py):
all 31 public fixture names are present. The previously unsupported `live_server`,
`django_db_serialized_rollback`, and `django_isolated_apps` fixtures now implement
their respective server, restoration, and registry behavior. The suffix variants
apply their configured environment identities; fixture-name parity does not imply
native parallel-worker integration. `django_db_modify_db_settings` remains an
override point for consumer configuration.

## Module exports

`rustest_django.__version__`, `DjangoAssertNumQueries`, `DjangoCaptureOnCommitCallbacks`,
`Settings`, `DjangoDbBlocker`, `django_db` (the class decorator).

`rustest_django.asserts`: Django-specific `assert*` methods declared on `SimpleTestCase`,
`TestCase`, `TransactionTestCase`, `LiveServerTestCase` and `MessagesTestMixin`, as
module-level functions, with an `asserts.pyi` stub. Inherited unittest assertions such
as `assertEqual`, `assertTrue`, and `assertRaises` are not exported; use Python
assertions and `rustest.raises` when rewriting those calls.

## Remaining compatibility limits

Unittest-style tests fail per method with an explicit guard (see the unittest
decision). Class-level and module-level markers remain subject to rustest's
propagation limits described above. Native parallel execution also requires a
reliable worker identity before shared database names can be isolated
automatically. See the
[unsupported-feature inventory](../../site-docs/reference/unsupported.md).

Guarded failures use the implemented `rustest-django: ` prefix and give a concrete
alternative when one is available, as recorded in the
[error-message design](../plans/2026-09-16-error-messages-design.md).
