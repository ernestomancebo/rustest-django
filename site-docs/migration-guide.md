# Migration Guide

Moving an existing pytest-django test suite to rustest-django. Three changes, in order.

!!! tip "Have Claude Code do it"
    The [`rustest-django-migrate-tests` skill](agent-skills.md) applies these steps for
    you, including the `TestCase` rewrite.

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

A handful of pytest-django features remain outside rustest-django v1's supported tier:

- **Unittest-style Django `TestCase` subclasses** (`SimpleTestCase`, `TestCase`,
  `TransactionTestCase`, `LiveServerTestCase`). rustest runs their methods but discards
  the result, so every method would otherwise silently report as passed regardless of
  what actually happened. Rewrite these as plain functions using the `db`/`transactional_db`
  fixtures, or exclude those test paths from your rustest run for now.
- **Class-level marks and module-level `pytestmark`.** See
  [Class and module marks](reference/unsupported.md#class-and-module-marks) for the
  current limit and the workaround.

The live-server, serialized-rollback, and isolated-app fixtures are implemented, along
with the `urls`, `django_isolate_apps`, and `ignore_template_errors` function-level
markers. See the [fixture](reference/fixtures.md) and [marker](reference/markers.md)
references for their lifetimes and arguments.

Pytest-Django runner flags map to [environment variables or project
configuration](reference/configuration.md). Existing Django settings in `pytest.ini`
or pytest's TOML sections provide fallbacks; pytest `addopts` is not forwarded to
rustest. For django-configurations projects, install the `configurations` extra.

The [remaining runner boundaries](reference/unsupported.md) cover unittest results,
mark propagation, and automatic parallel-worker identity.
