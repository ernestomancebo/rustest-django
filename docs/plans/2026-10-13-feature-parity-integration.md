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
