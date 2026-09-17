# Migration Guide

Moving an existing pytest-django test suite to rustest-django. Three changes, in order.

## 1. Swap the plugin registration

Replace pytest-django's plugin registration with rustest-django's fixture-module
registration in `conftest.py`:

```python
# before
pytest_plugins = ["pytest_django"]

# after
rustest_fixtures = ["rustest_django"]
```

(If you never wrote `pytest_plugins` explicitly -- pytest-django usually registers itself
via an entry point -- this line is simply new.)

## 2. Decide how your test files reference pytest

pytest-django tests almost always `import pytest` directly, for `@pytest.mark.django_db`
and similar. You have two options, and you don't have to convert every file the same way:

**Option A -- keep `import pytest`, run with `--pytest-compat`.** rustest installs a shim
into `sys.modules["pytest"]` so `pytest.mark`, `pytest.fixture`, `pytest.raises`, and
`pytest.fail` resolve to rustest's own objects. Your test files are untouched:

```bash
rustest --pytest-compat
```

This is the fastest path for a large suite -- no per-file edits.

**Option B -- rewrite imports to rustest's own names.** No flag needed, but every test
file that references `pytest.mark`/`pytest.fixture`/etc. needs its imports changed:

```python
# before
import pytest

@pytest.mark.django_db
def test_something(client):
    ...

# after
from rustest import mark

@mark.django_db
def test_something(client):
    ...
```

Either way, imports of pytest-django's own names change unconditionally (`--pytest-compat`
only shims the `pytest` module, not `pytest_django`):

```python
# before
from pytest_django.asserts import assertContains

# after
from rustest_django.asserts import assertContains
```

## 3. Worked example

From `examples/minimal-sqlite/` in this repo -- real Django app tests, shown pytest-django
style then rustest-django style (Option B, fully rewritten). Both versions pass; verified
by actually running each against its respective runner, not just written by hand.

**Before** (`tests/test_views.py`, pytest-django):

```python
import pytest

from blog.models import Post


@pytest.mark.django_db
def test_post_list_shows_published_posts(client):
    Post.objects.create(title="visible", published=True)
    Post.objects.create(title="hidden", published=False)

    response = client.get("/")

    content = response.content.decode()
    assert "visible" in content
    assert "hidden" not in content


def test_rf_builds_a_request(rf):
    request = rf.get("/")

    assert request.path == "/"
```

**After**:

```python
from rustest import mark

from blog.models import Post


@mark.django_db
def test_post_list_shows_published_posts(client):
    Post.objects.create(title="visible", published=True)
    Post.objects.create(title="hidden", published=False)

    response = client.get("/")

    content = response.content.decode()
    assert "visible" in content
    assert "hidden" not in content


def test_rf_builds_a_request(rf):
    request = rf.get("/")

    assert request.path == "/"
```

The fixtures themselves (`client`, `rf`, `admin_client`, `transactional_db`, ...) are
looked up by name and need no changes at all, same as pytest-django. Only the *import and
marker spelling* changes -- and it has to change consistently within a file. A file that
still says `import pytest` needs `--pytest-compat` running for its `@pytest.mark.django_db`
to be recognized at all (see Option A above). Mixing an unrewritten `import pytest` file
into a run *without* `--pytest-compat` means its marks are silently invisible, and any test
needing database access fails with `Database access not allowed, use the django_db mark,
or the db or transactional_db fixtures to enable it.` -- worth knowing so it doesn't look
like a rustest-django bug the first time you see it.

## What doesn't migrate

A handful of pytest-django features are intentionally unsupported in rustest-django v1
and fail loudly rather than silently doing the wrong thing:

- **Unittest-style Django `TestCase` subclasses** (`SimpleTestCase`, `TestCase`,
  `TransactionTestCase`, `LiveServerTestCase`). rustest runs their methods but discards
  the result, so every method would otherwise silently report as passed regardless of
  what actually happened. Rewrite these as plain functions using the `db`/`transactional_db`
  fixtures, or exclude those test paths from your rustest run for now.
- `live_server`, `django_db_serialized_rollback`, `django_isolated_apps` fixtures, and the
  `urls`/`ignore_template_errors` markers. See [Unsupported features](reference/unsupported.md)
  for what each one does instead, where an alternative exists.

If your suite uses any of these, you'll see a `rustest-django: ...` error naming exactly
what's unsupported the moment a test touches it -- that's the guard working as intended,
not a bug.
