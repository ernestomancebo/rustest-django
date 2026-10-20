# Fixtures

Every fixture below is looked up by name, exactly like pytest-django -- request it as a
test parameter, or override it by name from your own `conftest.py`.

## Database

- **`db`** -- wraps the test in a transaction, rolled back afterward. Required by any test
  that touches the database, directly or via `@mark.django_db`.
  A fixture that needs the database in its own body can request `db` or `transactional_db`
  as a parameter, or call `request.getfixturevalue("db")` while it runs. `django_db_reset_sequences`,
  `django_db_serialized_rollback` and `live_server` must be parameters.
- **`transactional_db`** -- like `db`, but truncates tables afterward instead of rolling
  back a transaction. Needed by tests that themselves rely on transaction behavior (e.g.
  testing `on_commit` callbacks).
- **`django_db_reset_sequences`** -- like `transactional_db`, and also resets
  auto-increment sequences, so new rows get predictable IDs starting from 1.
- **`django_db_serialized_rollback`** -- requests restoration of the database snapshot
  created during setup. Combine with `transactional_db` or `live_server` when tests
  need real transactions while preserving migration-created data.
- **`django_db_setup`**, **`django_db_blocker`**, **`django_db_createdb`**,
  **`django_db_keepdb`**, **`django_db_use_migrations`** -- session-scoped internals
  controlling how the test database is created/migrated/torn down. Override by name if
  you need custom database setup; most consumers never touch these directly.
- **`django_db_modify_db_settings`**, **`django_db_modify_db_settings_parallel_suffix`**,
  **`django_db_modify_db_settings_tox_suffix`**, **`django_db_modify_db_settings_xdist_suffix`**
  -- apply database-name suffixes before test database creation. Tox identities come
  from `TOX_PARALLEL_ENV`; worker identities come from `RUSTEST_DJANGO_DB_SUFFIX`, falling
  back to `PYTEST_XDIST_WORKER`. In-memory SQLite and database mirrors are excluded.
  Override `django_db_modify_db_settings` for project-specific setup. Rustest's
  experimental workers do not supply a supported automatic worker identity here;
  configure a distinct suffix for each separate process.

## Live server

**`live_server`** -- a session-scoped real Django HTTP server. Use `live_server.url`,
`str(live_server)`, or `live_server + "/path/"` for its address. Startup is deferred
until the address is used; requesting it activates transactional database access for
the test, including when requested through a session-scoped browser fixture.

The test and server use separate threads, so database writes must be committed to be
visible between them. The fixture handles shared in-memory SQLite connections and
stops the server at session teardown. Configure its host and port through the
[configuration reference](configuration.md).

## App registry

**`django_isolated_apps`** -- the isolated registry created by
[`@mark.django_isolate_apps`](markers.md#markdjango_isolate_apps). Requesting this
fixture without the companion marker raises an error. Registry changes are restored
after each marked test.

## Clients and users

- **`client`** -- a `django.test.Client` instance.
- **`async_client`** -- a `django.test.AsyncClient` instance, for `async def` tests.
- **`rf`** -- a `django.test.RequestFactory` instance.
- **`async_rf`** -- an `AsyncRequestFactory` instance.
- **`admin_client`** -- a `client` already logged in as the `admin_user`.
- **`admin_user`** -- a superuser created via `django_user_model`, database-backed.
- **`django_user_model`** -- the active user model (`django.contrib.auth.get_user_model()`).
- **`django_username_field`** -- the user model's username field name (usually
  `"username"`).

## Settings

- **`settings`** -- a `Settings` object for overriding `django.conf.settings` values for
  the duration of a single test; changes are automatically reverted afterward.

## Mail

- **`mailoutbox`** -- the list of `django.core.mail.EmailMessage` objects sent during the
  test (Django's test mail backend), auto-cleared between tests.
- **`django_mail_patch_dns`**, **`django_mail_dnsname`** -- control the DNS name used when
  generating `Message-Id` headers in outgoing test mail, for deterministic assertions.

## Query assertions

- **`django_assert_num_queries`** -- context manager/decorator asserting an exact number
  of database queries ran.
- **`django_assert_max_num_queries`** -- like the above, but asserts an upper bound rather
  than an exact count.
- **`django_capture_on_commit_callbacks`** -- context manager capturing
  `transaction.on_commit(...)` callbacks so they can be invoked and asserted on explicitly.

## Module-level exports

Not fixtures, but exported from `rustest_django` directly: `__version__`,
`DjangoAssertNumQueries`, `DjangoCaptureOnCommitCallbacks`, `Settings`, `DjangoDbBlocker`
(the underlying types behind `django_assert_num_queries`, `django_capture_on_commit_callbacks`,
`settings`, and `django_db_blocker`, if you need to reference the type directly).
The `django_db` class decorator is also exported; see [Markers](markers.md).

`rustest_django.asserts` -- Django-specific `assert*` methods declared on `SimpleTestCase`,
`TestCase`, `TransactionTestCase`, `LiveServerTestCase`, and (on Django 5.0+)
`MessagesTestMixin`, exposed
as plain module-level functions (e.g. `rustest_django.asserts.assertContains(...)`), for
suites that imported helpers from `pytest_django.asserts`. Inherited unittest methods
such as `assertEqual`, `assertTrue`, and `assertRaises` are not module exports. Use
Python assertions or `rustest.raises` when rewriting those calls.
