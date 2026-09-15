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

## Marker

`@mark.django_db(transaction=False, reset_sequences=False, databases=None,
serialized_rollback=False, available_apps=None)`, positional in that order, from
`rustest.mark` (identical object as `pytest.mark` under `--pytest-compat`). Same defaults
and validation as pytest-django; unknown kwargs raise `TypeError`.

Function-level marks work directly under rustest 0.18. Class-level marks do not
propagate to methods (rustest limitation, reported upstream as
[rustest#143](https://github.com/Apex-Engineers-Inc/rustest/issues/143)); use the
`rustest_django.django_db(...)` class decorator instead, which applies the marker to
every `test*` method at class-decoration time. See `docs/spec/upstream.md`. Module-level
`pytestmark` has no equivalent in v1.

## Fixtures

Database and lifecycle:
`db`, `transactional_db`, `django_db_reset_sequences`, `django_db_setup`,
`django_db_blocker`, `django_db_createdb`, `django_db_keepdb`, `django_db_use_migrations`,
`django_db_modify_db_settings`, `django_db_modify_db_settings_parallel_suffix`,
`django_db_modify_db_settings_tox_suffix`, `django_db_modify_db_settings_xdist_suffix`
(name kept, no-op), `django_test_environment`.

Clients and users:
`client`, `async_client`, `rf`, `async_rf`, `admin_client`, `admin_user`,
`django_user_model`, `django_username_field`.

Settings, mail, queries:
`settings`, `mailoutbox`, `django_mail_patch_dns`, `django_mail_dnsname`,
`django_capture_on_commit_callbacks`, `django_assert_num_queries`,
`django_assert_max_num_queries`.

Autouse internals, private names, not part of the contract: marker activation, mailbox
autoclear, `Site` cache clear, the unittest-style guard, the unsupported-marker guard.

All session fixtures above are overridable by name from a consumer `conftest.py`.

## Module exports

`rustest_django.__version__`, `DjangoAssertNumQueries`, `DjangoCaptureOnCommitCallbacks`,
`Settings`, `DjangoDbBlocker`.

`rustest_django.asserts`: every `assert*` method of `SimpleTestCase`, `TestCase`,
`TransactionTestCase`, `LiveServerTestCase` and `MessagesTestMixin`, as module-level
functions, with an `asserts.pyi` stub.

## Unsupported names

Every pytest-django name outside the list above exists and fails loudly:

- Fixtures `live_server`, `django_db_serialized_rollback`, `django_isolated_apps` are
  defined and raise a `rustest_django` error naming the feature and stating it is
  unsupported in v1.
- Markers `urls` and `ignore_template_errors` are detected by an autouse fixture and raise
  the same way.
- Unittest-style tests fail per method (see the unittest decision).

Exact message text is decided with the error UX of unsupported features.
