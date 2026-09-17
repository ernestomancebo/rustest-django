---
id: 20260916090300
title: Markers
tags: [reference]
---

# Markers

## `@mark.django_db`

```python
@mark.django_db(transaction=False, reset_sequences=False, databases=None,
                 serialized_rollback=False, available_apps=None)
```

From `rustest.mark` (the same object as `pytest.mark` when running with
`--pytest-compat`). Same defaults and kwarg validation as pytest-django's `django_db`
mark -- unknown kwargs raise `TypeError`.

- `transaction=True` behaves like requesting the `transactional_db` fixture instead of
  `db`.
- `databases=[...]` grants access to additional databases beyond `default`, for
  multi-database projects.
- `reset_sequences=True` behaves like `django_db_reset_sequences`.
- `serialized_rollback=True` passes straight through to Django's `TestCase` machinery, same
  as pytest-django -- meaningful together with `transaction=True`, since it's the
  non-atomic (`TransactionTestCase`-based) path that restores serialized data after
  truncating tables. This is distinct from the separate `django_db_serialized_rollback`
  *fixture*, which is unsupported -- see [Unsupported features](unsupported.md).

Applying the mark is equivalent to requesting the `db` fixture (or `transactional_db`,
etc., depending on kwargs) -- you don't need both.

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
