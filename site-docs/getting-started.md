# Getting Started

## Install

```bash
pip install rustest-django
# or
uv add rustest-django
```

This pulls in `rustest` and `django` as dependencies. rustest-django supports Python 3.10+
and Django 4.2, 5.2, and 6.1.

## Wire it up

Add one line to your project's `conftest.py`:

```python
# conftest.py
rustest_fixtures = ["rustest_django"]
```

rustest-django needs to know which Django settings module to use. Either set
`DJANGO_SETTINGS_MODULE` as usual, or point at it directly:

```toml
# pyproject.toml
[tool.rustest-django]
settings_module = "myproject.settings"
```

See [Configuration](reference/configuration.md) for every available key.

## Write a test

```python
# test_posts.py
from rustest import mark

from blog.models import Post


@mark.django_db
def test_creating_a_post():
    Post.objects.create(title="hello")

    assert Post.objects.count() == 1
```

`@mark.django_db` opts a test into database access, wrapped in a transaction that's
rolled back afterward -- same behavior as pytest-django's `django_db` mark.

## Run it

```bash
rustest
```

That's the full setup. If any of your test files still do `import pytest`, see the
[Migration Guide](migration-guide.md)'s note on `--pytest-compat` before running.
