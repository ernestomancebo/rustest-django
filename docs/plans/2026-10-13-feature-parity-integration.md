# Fixture, marker, and configuration integration

Integration branch: `integration/pytest-django-parity`.

## Scope

Implement the remaining plugin features identified by the documentation audit:
live server and its configuration, standalone serialized rollback, app-registry
isolation, URL overrides, strict template-variable checking and exemptions,
django-configurations bootstrap, database suffixes, pytest configuration fallback,
and marker/configuration validation.

Project defaults belong in configuration. Per-test setup and cleanup remain fixture
or marker behavior. Django unittest outcomes and class/module mark propagation remain
runner limitations, outside this plugin implementation.

## Agreed test seam

Use the rustest CLI seam already approved in this session: write a consumer project
with `rustest_fixtures = ["rustest_django"]`, invoke the real runner, and observe
test results, HTTP responses, rendered templates, and public Django behavior.
This catches fixture ordering, bootstrap, isolation, cleanup, and configuration
integration. It does not prove browser automation or every upstream runner feature.

Each implementation proceeds one failing consumer test and one minimal implementation
at a time, following `mattpocock-skills:tdd`. Preserve red/green evidence in the work
report. Existing regression tests remain part of integration validation.

## Worktrees and ownership

| Branch | Worktree | Responsibility |
|---|---|---|
| `feat/config-compat` | `/private/tmp/rustest-django-config` | Config discovery/types, new options, configuration-class bootstrap |
| `feat/markers-compat` | `/private/tmp/rustest-django-markers` | App registry, URL, and template markers/fixtures |
| `feat/live-server-db` | `/private/tmp/rustest-django-live-server` | Live server, rollback fixture, suffixes, database marker validation |

The parent integrates the feature branches, resolves shared exports, updates docs and
dependency locks, and runs the combined regression, parity, lint, type, and build checks.

## Configuration contract

Native project keys remain under `[tool.rustest-django]`. Add `configuration`,
`live_server_host`, `live_server_port`, and `fail_on_template_vars`, with environment
overrides. Pytest configuration supplies compatible fallbacks; document discovery and
precedence. Do not forward pytest CLI flags through an unimplemented runner parser.

`django-configurations` is an optional runtime extra and a development test dependency.
Server and template defaults do not change ordinary tests that do not request them.

## Integration acceptance

- All new consumer tests and existing applicable regression tests pass.
- Example suites retain pytest/rustest outcome parity.
- Exercise the supported Django release families and PostgreSQL when available.
- Ruff, type checks, strict documentation build, and package build pass.
- Public docs describe implemented behavior and remaining runner boundaries.

## Review findings and follow-up

The first integrated checks passed across Django 4.2, 5.2, and 6.1, with 147 tests
per SQLite run, followed by a 148-test PostgreSQL run after a cleanup regression
was added. All three original example suites retained exact pytest/rustest outcomes,
including the new real HTTP database-visibility case.

Independent review found fixture-discovery cases that required further red/green
cycles: `usefixtures` marks, consumer overrides, and direct parametrized values.
The fixes preserve consumer fixture definitions and distinguish values from fixtures.
A consumer test that named private isolation machinery was replaced by a public
`admin_user` dependency.

The marker review also found that policies must start before consumer fixture setup.
The activation adapter addresses this using normal runner-managed fixture lifetime;
final checks include fixture setup, test/fixture failure cleanup, and dual-runner
compatibility.

Cross-version verification exposed an existing unconditional import of Django 5.0's
messages assertion mixin on Django 4.2. Assertion exports now follow the installed
Django version. CI commands use `uv run --no-sync` after matrix pins: a direct probe
confirmed plain `uv run` replaces a manually pinned Django with the locked version.

The final activation review also checked direct calls between test functions and
helper-only package imports. Both had consumer CLI reproducers before their fixes.
The adapter preserves ordinary positional/keyword calls and original globals, and
only activates within directories declaring the fixture module. Independent review
reported no outstanding findings at commit `618edb9`.

Package inspection found pre-existing local worktrees in the default source archive.
The source-distribution target now excludes `.claude`, `prototypes`, and generated
skill-evaluation reports; the corrected archive retains the library source.

## Final verification

Local runs used Python 3.12.11 with explicitly selected Django versions, without
resynchronizing version pins:

| Environment | Full suite |
|---|---|
| Django 4.2.30 / SQLite | 171 passed |
| Django 5.2.18 / SQLite | 171 passed |
| Django 6.1.1 / SQLite | 171 passed |
| Django 6.1.1 / PostgreSQL 16 | 171 passed |

The independent final review reported no outstanding findings after the direct-call
and helper-import fixes. New feature and review regressions exercise the agreed
consumer CLI seam. Class/module marks, Django unittest outcomes, and native automatic
worker identity remain documented upstream runner boundaries.

Final exact-outcome parity checks passed for all examples: minimal SQLite (15 tests),
multi-database (6), async views (4), and real HTTP/database sharing against PostgreSQL
(15). Ruff, type checking, all pre-commit hooks, strict MkDocs, and distribution metadata
checks passed. A fresh wheel installation also exercised URL markers and live-server
database visibility independently of the editable source checkout.
