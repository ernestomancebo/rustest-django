# rustest-django

**rustest-django** is [rustest](https://github.com/apex-engineers-inc/rustest)'s Django
integration -- a port of [pytest-django](https://pytest-django.readthedocs.io/), exposed
as a rustest fixture module.

If you have an existing pytest-django test suite, the goal is that it runs under rustest
with an import-path swap and nothing else. Same fixtures, same marker, same test files.

## Quick example

```toml
# pyproject.toml
[project]
dependencies = ["rustest-django"]
```

```python
# conftest.py
rustest_fixtures = ["rustest_django"]
```

```python
# test_posts.py
from rustest import mark

from blog.models import Post


@mark.django_db
def test_creating_a_post():
    Post.objects.create(title="hello")

    assert Post.objects.count() == 1
```

That's the whole integration surface -- one line in `conftest.py`. From there:

- **[Getting Started](getting-started.md)** walks through installing rustest-django and
  running your first test.
- **[Migration Guide](migration-guide.md)** covers moving an existing pytest-django suite
  over.
- **Reference** documents the [fixtures](reference/fixtures.md),
  [markers](reference/markers.md), [configuration](reference/configuration.md), and
  [unsupported features](reference/unsupported.md) in detail.

## Why rustest-django exists

rustest is a from-scratch Python test runner, not a pytest plugin host -- it has no
plugin/hook system, so pytest-django itself can't just be installed and used. rustest-django
reimplements pytest-django's fixtures and marker on rustest's own primitives, keeping the
public surface identical.
