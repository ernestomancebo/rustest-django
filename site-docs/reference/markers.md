# Markers

## `@mark.django_db`

```python
@mark.django_db(transaction=False, reset_sequences=False, databases=None,
                 serialized_rollback=False, available_apps=None)
```

From `rustest.mark` (the same object as `pytest.mark` when running with
`--pytest-compat`). Options accept positional arguments in the order shown above
or keyword arguments. For example, `@mark.django_db(True)` and
`@mark.django_db(transaction=True)` both request transactional isolation. Unknown
keywords, duplicate values, and too many positional arguments fail with a
`rustest-django: ` error rather than silently changing the test's isolation.

- `transaction=True` behaves like requesting the `transactional_db` fixture instead of
  `db`.
- `databases=[...]` grants access to additional databases beyond `default`, for
  multi-database projects.
- `reset_sequences=True` behaves like `django_db_reset_sequences`.
- `serialized_rollback=True` passes straight through to Django's `TestCase` machinery, same
  as pytest-django -- meaningful together with `transaction=True`, since it's the
  non-atomic (`TransactionTestCase`-based) path that restores serialized data at
  setup after earlier transactional tests flushed the tables. The
  `django_db_serialized_rollback` fixture requests the same
  restoration behavior and can be combined with `transactional_db` or `live_server`.

Applying the mark is equivalent to requesting the `db` fixture (or `transactional_db`,
etc., depending on kwargs) -- you don't need both.

## `@mark.urls`

Use a different URL configuration for one test:

```python
from rustest import mark


@mark.urls("my_app.test_urls")
def test_alternate_routes(client):
    assert client.get("/test-route/").status_code == 200
```

The marker accepts one URLconf module name or imported module, either positionally
or as `urls=...`. It overrides `ROOT_URLCONF`, resets URL resolver caches and the
current URLconf. It restores the original setting and clears resolution state
when the test finishes, including after a test or fixture failure. Set
`ROOT_URLCONF` in Django's test settings for a
suite-wide default.

## `@mark.django_isolate_apps`

Create a temporary app registry for models defined inside a test:

```python
from django.db import models
from rustest import mark


@mark.django_isolate_apps("django.contrib.contenttypes")
def test_dynamic_model(django_isolated_apps):
    class Temporary(models.Model):
        class Meta:
            app_label = "contenttypes"

    assert django_isolated_apps.get_model("contenttypes", "Temporary") is Temporary
```

Pass one or more app module names as positional strings. The
`django_isolated_apps` fixture returns that isolated registry and requires this
marker. Django's original model registry is restored after the test or a failed
fixture setup. App isolation controls model registration; it does not create
database tables or grant database access.

## `@mark.ignore_template_errors`

The project setting `fail_on_template_vars = true` in `[tool.rustest-django]`
enables strict checking of missing variables rendered by configured Django
template backends. Errors identify the missing variable and template origin when
available. Missing values in template conditionals remain allowed; a missing
rendered variable fails even if followed by a `default` filter.

Use this argument-free marker to allow normal template rendering in a selected
test:

```python
from django.template import engines
from rustest import mark


@mark.ignore_template_errors
def test_template_fallback():
    template = engines["django"].from_string('{{ missing|default:"fallback" }}')
    assert template.render({}) == "fallback"
```

`@mark.ignore_template_errors()` is also accepted. Checking resumes for subsequent
tests, including after rendering or fixture failures. The marker exempts a test
from the project policy; it does not enable strict checking itself. See
[Configuration](configuration.md) for environment and pytest setting fallbacks.

## Function vs. class marks

Function-level marks work directly:

```python
@mark.django_db
def test_something():
    ...
```

**Class-level marks do not propagate to methods** -- a current rustest limitation (no
class-level mark propagation), reported upstream as
[rustest#143](https://github.com/apex-engineers-inc/rustest/issues/143). Module-level
`pytestmark = [pytest.mark.django_db]` has no equivalent either.
These limitations apply to all markers on this page.

For a whole `TestCase`-free class of test functions that all need `django_db`, use the
`rustest_django.django_db` class decorator instead, which applies the marker to every
`test*` method at class-decoration time:

```python
from rustest_django import django_db


@django_db(transaction=True)
class TestSomething:
    def test_one(self):
        ...

    def test_two(self):
        ...
```

This takes the same keyword arguments as `@mark.django_db(...)`.
