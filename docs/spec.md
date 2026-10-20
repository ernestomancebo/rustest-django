# rustest-django v1 spec

Wayfinder map: [ernestomancebo/rustest-django#1](https://github.com/ernestomancebo/rustest-django/issues/1).
The map is complete and the supported v1 tier is implemented. The latest PyPI release is
[0.0.2](https://pypi.org/project/rustest-django/0.0.2/); "v1" describes the design scope,
not a published 1.0 version. The sections below record the implemented decisions and
the remaining compatibility boundaries.

## Goals and contract

- **Port**: preserve pytest-django's public names within the supported tier, with
  compatibility boundaries documented; internals use rustest primitives.
- **Compat contract**: a consumer migrates with an import-path swap only
  (`pytest_django` → `rustest_django`, see [Public API § Name
  swap](./spec/api.md#name-swap)) within the supported tier. Invalid marker/configuration
  arguments and unsupported Django unittest tests fail
  loudly. Runner boundaries are listed in
  [Public API § Remaining compatibility limits](./spec/api.md#remaining-compatibility-limits).
- **Supported tier v1**:
  - **T1** (full): settings, setup, `db`, `transactional_db`, `django_db`, `client`,
    `rf`, `admin_*`, `django_user_model`, `settings`, `mailoutbox`,
    `rustest_django.asserts`.
  - **T2** (picks): `django_assert_num_queries`/`max`, `async_client`/`async_rf`,
    multi-database.
  - **T3** (pick): reuse-db as a runner option.
  - Follow-up ports add live server, standalone serialized rollback, app isolation,
    URL overrides, strict templates, configuration-class bootstrap, and database suffixes.
    Remaining boundaries are in [Public API § Remaining compatibility limits](./spec/api.md#remaining-compatibility-limits).

Glossary: [CONTEXT.md](../CONTEXT.md).

## Architecture

rustest's sole extension point is a **fixture module** loaded via `rustest_fixtures =
[...]` in a consumer's `conftest.py`; rustest-django *is* that module. rustest imports it
right after the declaring conftest and before any test module — the only point early
enough to run `django.setup()` before test modules import models (see [Configuration §
When Django is set up](./spec/configuration.md#when-django-is-set-up)). Import-time
errors from a fixture module are silently swallowed by rustest, so rustest-django
re-raises them from a session autouse fixture instead, so every test fails with the same
message rather than the run silently proceeding without Django configured.

Per-test behaviour rests on two pieces built for the whole session:

- **DB blocker**: raises on any database access with no isolation active. Lifted by an
  isolation or an explicit unblock. See [DB isolation § DB blocker](./spec/db-isolation.md#db-blocker).
- **Isolation engine**: reuses Django's own `TestCase`/`TransactionTestCase` internals,
  not a hand-rolled `atomic()` + flush. Full detail and rationale: [DB
  isolation](./spec/db-isolation.md), [ADR
  0001](./adr/0001-db-isolation-on-django-testcase-internals.md).

Markers are read via `request.node.get_closest_marker`, which only reaches
function-level marks under rustest 0.18; class-level marks and `pytestmark` don't
propagate, worked around by the `rustest_django.django_db` class decorator (see
[Upstream relationship](./spec/upstream.md)).

## Public API

Fixture and marker list, name-swap mechanics: [docs/spec/api.md](./spec/api.md).

## Configuration

Settings discovery, `pyproject.toml`/env precedence, failure behaviour:
[docs/spec/configuration.md](./spec/configuration.md).

## DB isolation

Isolation modes, test database lifecycle, private-API boundary:
[docs/spec/db-isolation.md](./spec/db-isolation.md).

## Async support

Native async tests, loop-scope constraint, DB-access caveat:
[docs/spec/async.md](./spec/async.md).

## Unsupported test styles

`unittest`-style Django `TestCase` support (out for v1):
[docs/spec/unittest-support.md](./spec/unittest-support.md).

## Unsupported-feature behaviour

Django unittest-style tests fail loudly, as do invalid configuration and marker
arguments. Messages use the `rustest-django: ` prefix and include an alternative when
one exists. Fixture and marker ports are implemented; class/module mark propagation,
Django unittest result reporting, and automatic native parallel-worker identity remain
runner boundaries. See [Remaining compatibility limits](./spec/api.md#remaining-compatibility-limits).

## Example projects and CI

Three parity example projects, the parity oracle, and the CI matrix:
[docs/spec/testing-and-ci.md](./spec/testing-and-ci.md).

## Packaging and versioning

- **Distribution**: standalone repo, PyPI package `rustest-django`, import
  `rustest_django`.
- **Versions**: Python 3.10+; Django 4.2 LTS, 5.x, 6.x (6.x requires Python ≥3.12). Full
  CI matrix: [testing-and-ci.md § CI matrix](./spec/testing-and-ci.md#ci-matrix).
- **rustest version target**: `rustest>=0.18,<1.0`. Detail:
  [docs/spec/upstream.md](./spec/upstream.md).
- **Tooling**: uv, hatchling, ruff, `ty` for type checking.
- **License**: BSD-3-Clause, pytest-django copyright retained.

## Upstream relationship

Gaps reported to rustest, workarounds shipped in the meantime:
[docs/spec/upstream.md](./spec/upstream.md).

## Deferred

The previously deferred plugin fixtures, markers, and configuration integrations are
implemented. The remaining work depends on upstream runner capabilities:

- Django unittest outcome reporting and class/module marker propagation.
- Automatic worker identity and database isolation for native rustest parallel runs.
- Plugin CLI flag registration; supported Django options use project configuration
  and environment overrides instead.

See the [runner-boundary reference](../site-docs/reference/unsupported.md). The
implementation and verification plan is recorded in
[feature integration](plans/2026-10-13-feature-parity-integration.md).

## Completed follow-ups

The original map deferred these tasks, which are now implemented:

| Task | Implementation |
|---|---|
| Fixture, marker, and configuration ports | [Integration plan](plans/2026-10-13-feature-parity-integration.md); live server ([#25](https://github.com/ernestomancebo/rustest-django/issues/25)), rollback/app-isolation fixtures, URL/template markers, configuration-class bootstrap, INI fallbacks, suffixes, and argument/type validation. |
| Error-message shapes | [Design](plans/2026-09-16-error-messages-design.md) and [PR #30](https://github.com/ernestomancebo/rustest-django/pull/30); shared prefix and alternatives in configuration, bootstrap, fixture, and unittest guards. |
| Consumer migration guide | [Published guide source](../site-docs/migration-guide.md), delivered with [PR #33](https://github.com/ernestomancebo/rustest-django/pull/33). |
| Release process and trusted publishing | [Release design](plans/2026-09-16-release-process-design.md), [PR #29](https://github.com/ernestomancebo/rustest-django/pull/29), and completed [publisher registration #28](https://github.com/ernestomancebo/rustest-django/issues/28); release `v0.0.1` is published. |
| Hosted documentation | [Docs-site design](plans/2026-09-16-docs-site-design.md) and completed [RTD registration #31](https://github.com/ernestomancebo/rustest-django/issues/31); `stable` and `latest` are built. |

Remaining distribution follow-ups are the upstream listing in
[#26](https://github.com/ernestomancebo/rustest-django/issues/26) and the RTD default-version
setting in [#32](https://github.com/ernestomancebo/rustest-django/issues/32). Neither blocks
installing the published package.
