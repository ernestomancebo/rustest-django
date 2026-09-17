# rustest-django

[![Docs](https://readthedocs.org/projects/rustest-django/badge/?version=latest)](https://rustest-django.readthedocs.io/en/latest/)

Django integration for [rustest](https://github.com/apex-engineers-inc/rustest): a port of
[pytest-django](https://github.com/pytest-dev/pytest-django) exposed as a rustest fixture module.

Goal: existing pytest-django test suites run under rustest with only an import-path swap.

## Status

v1 is implemented and CI-verified: configuration resolution, the DB isolation engine,
the fixture-module entry point, the full T1/T2 fixture surface (`client`/`rf`, `admin_*`,
`settings`, `mailoutbox`, query-assertion helpers, DB lifecycle fixtures), the
unittest-style and unsupported-feature guards, `rustest_django.asserts`, and the
`rustest_django.django_db` class decorator. Not yet released to PyPI — see
[#23](https://github.com/ernestomancebo/rustest-django/issues/23).

The full design is written up in [`docs/spec.md`](docs/spec.md), which links out to a
section per topic (configuration, DB isolation, the public API, async support, testing
and CI). It's a locked spec, not a proposal: every section there describes what's
actually built, not a plan. Rendered docs: <https://rustest-django.readthedocs.io/en/latest/>.

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

That's the whole integration surface. From there, an existing pytest-django test suite
runs by swapping `pytest_django` imports for `rustest_django` (see
[`docs/spec/api.md`](docs/spec/api.md#name-swap)) and running rustest with
`--pytest-compat` if any test files still `import pytest` directly.

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
