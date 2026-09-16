---
id: 20260916090200
title: Fixtures
tags: [reference]
---

# Fixtures

Every fixture below is looked up by name, exactly like pytest-django -- request it as a
test parameter, or override it by name from your own `conftest.py`.

## Database

- **`db`** -- wraps the test in a transaction, rolled back afterward. Required by any test
  that touches the database, directly or via `@mark.django_db`.
- **`transactional_db`** -- like `db`, but truncates tables afterward instead of rolling
  back a transaction. Needed by tests that themselves rely on transaction behavior (e.g.
  testing `on_commit` callbacks).
- **`django_db_reset_sequences`** -- like `transactional_db`, and also resets
  auto-increment sequences, so new rows get predictable IDs starting from 1.
- **`django_db_setup`**, **`django_db_blocker`**, **`django_db_createdb`**,
  **`django_db_keepdb`**, **`django_db_use_migrations`** -- session-scoped internals
  controlling how the test database is created/migrated/torn down. Override by name if
  you need custom database setup; most consumers never touch these directly.
- **`django_db_modify_db_settings`**, **`django_db_modify_db_settings_parallel_suffix`**,
  **`django_db_modify_db_settings_tox_suffix`**, **`django_db_modify_db_settings_xdist_suffix`**
  -- names kept for drop-in compatibility with pytest-django `conftest.py` overrides; the
  parallel/tox/xdist-suffix variants are no-ops in rustest-django (rustest runs
  sequentially, so there's no parallel worker to suffix a database name for).

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

`rustest_django.asserts` -- every `assert*` method from Django's `SimpleTestCase`,
`TestCase`, `TransactionTestCase`, `LiveServerTestCase`, and `MessagesTestMixin`, exposed
as plain module-level functions (e.g. `rustest_django.asserts.assertContains(...)`), for
suites that used pytest-django's `django_assert_*` import style.
