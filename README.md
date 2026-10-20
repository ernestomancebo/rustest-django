# rustest-django

[![Docs](https://readthedocs.org/projects/rustest-django/badge/?version=stable)](https://rustest-django.readthedocs.io/en/stable/)

Django integration for [rustest](https://github.com/apex-engineers-inc/rustest): a port of
[pytest-django](https://github.com/pytest-dev/pytest-django) exposed as a rustest fixture module.

Goal: existing pytest-django test suites run under rustest with only an import-path swap.

## Status

The v1 supported tier is implemented and CI-verified: configuration resolution, the DB
isolation engine, the fixture-module entry point, T1 core and selected T2 fixtures
(`client`/`rf`, `admin_*`, `settings`, `mailoutbox`, query-assertion helpers, DB lifecycle
fixtures), the
unittest-style and unsupported-feature guards, `rustest_django.asserts`, and the
`rustest_django.django_db` class decorator. The first release,
[0.0.1](https://pypi.org/project/rustest-django/0.0.1/), is published on PyPI.
"v1" names the implementation scope; the package uses independent pre-1.0 versions.

The full design is written up in [`docs/spec.md`](docs/spec.md), which links out to a
section per topic (configuration, DB isolation, the public API, async support, testing
and CI), with [completed follow-ups and remaining work](docs/spec.md#completed-follow-ups).
Published-package docs: <https://rustest-django.readthedocs.io/en/stable/>.
Unreleased `main` docs: <https://rustest-django.readthedocs.io/en/latest/>.

The current source also implements live server, serialized rollback and app-registry
isolation, URL/template markers, django-configurations, and database suffixes. Project
options support native TOML, compatible pytest TOML, and INI fallbacks. See
[Configuration](site-docs/reference/configuration.md) and the remaining
[runner boundaries](site-docs/reference/unsupported.md). These additions are unreleased;
`stable` documents the published package.

## Using it

```toml
# pyproject.toml
[project]
dependencies = ["rustest-django"]
```

```python
# conftest.py
rustest_fixtures = ["rustest_django"]
```

That's the whole integration surface. Within the supported tier, an existing
pytest-django test suite runs by swapping `pytest_django` imports for `rustest_django` (see
[`docs/spec/api.md`](docs/spec/api.md#name-swap)) and running rustest with
`--pytest-compat` if any test files still `import pytest` directly.

## Agent skills

Two [agent skills](skills/) help a coding agent work with rustest-django in your project:

- [`rustest-django-migrate-tests`](skills/rustest-django-migrate-tests/SKILL.md): port a
  pytest-django suite, including rewriting Django `TestCase`-family classes.
- [`rustest-django-doctor`](skills/rustest-django-doctor/SKILL.md): diagnose a failing or
  confusing test as a suite problem or a known rustest-django limitation.

Install both with [skills.sh](https://skills.sh), which supports Claude Code and other agents:

```
npx skills add ernestomancebo/rustest-django
```

The agent loads a skill when your request matches its description, so ask for the task,
for example "migrate these tests to rustest-django".

## Example projects

[`examples/`](examples/) has three self-contained Django projects proving the
name-swap claim for real, unmodified pytest-django test files:

- [`minimal-sqlite`](examples/minimal-sqlite/): T1 core end to end.
- [`multi-db`](examples/multi-db/): the `databases=` marker kwarg and cross-database
  isolation.
- [`async-views`](examples/async-views/): `async_client`/`async_rf` and DB access from
  async tests.

Each one runs its `tests/` directory under both real `pytest` and
`rustest --pytest-compat`, and [`examples/compare_outcomes.py`](examples/compare_outcomes.py)
diffs the two outcome sets exactly. CI runs this across every supported Python/Django/DB
combination (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Development

```
uv sync
uv run pre-commit install
```

See the `Makefile` for the common commands (`make lint`, `make test`, `make build`,
`make parity-test`).

## Attribution

This project is a port of pytest-django, copyright (c) pytest-django contributors,
licensed under the BSD 3-Clause License. See `LICENSE`.
