# Configuration and settings discovery

Spec section for rustest-django v1. Decided in wayfinder ticket #10.

rustest has no CLI flag registration, no config object reachable from fixtures, and no
rootdir. rustest-django therefore reads project defaults and per-run overrides:

1. **Environment variables**: per-invocation overrides, the replacement for pytest-django's
   CLI flags.
2. **`[tool.rustest-django]` in `pyproject.toml`**: project defaults, the replacement for
   pytest-django's ini options.
3. **Compatible pytest settings**: TOML sections or `pytest.ini` / `.pytest.ini` fallbacks.

Precedence: environment > `[tool.rustest-django]` > selected pytest fallback >
built-in default.

## Keys

| key | type | default | env twin | pytest-django equivalent |
|---|---|---|---|---|
| `configuration` | str | none | `DJANGO_CONFIGURATION` | `--dc`, ini `DJANGO_CONFIGURATION` |
| `live_server_host` | str | `"localhost"` | `RUSTEST_DJANGO_LIVE_SERVER_HOST` | `--liveserver` host |
| `live_server_port` | int | `0` | `RUSTEST_DJANGO_LIVE_SERVER_PORT` | `--liveserver` port |
| `fail_on_template_vars` | bool | `false` | `RUSTEST_DJANGO_FAIL_ON_TEMPLATE_VARS` | `--fail-on-template-vars`, ini `FAIL_INVALID_TEMPLATE_VARS` |
| `settings_module` | str | none | `DJANGO_SETTINGS_MODULE` | `--ds`, ini `DJANGO_SETTINGS_MODULE` |
| `reuse_db` | bool | `false` | `RUSTEST_DJANGO_REUSE_DB` | `--reuse-db` |
| (env only) | bool | `false` | `RUSTEST_DJANGO_CREATE_DB` | `--create-db` |
| `migrations` | bool | `true` | `RUSTEST_DJANGO_MIGRATIONS` | `--migrations` / `--no-migrations` |
| `find_project` | bool | `true` | `RUSTEST_DJANGO_FIND_PROJECT` | ini `django_find_project` |
| `debug_mode` | `"true"` / `"false"` / `"keep"` | `"false"` | `RUSTEST_DJANGO_DEBUG_MODE` | ini `django_debug_mode` |

- `create_db` has no pyproject key: it is a one-shot action, not a project default. As in
  pytest-django it only cancels `reuse_db`.
- Env booleans accept `1`/`0`, `true`/`false`, `yes`/`no`, `on`/`off`, case-insensitive.
- Native TOML booleans require `true` or `false`; quoted strings are rejected.
- The legacy `DJANGO_LIVE_TEST_SERVER_ADDRESS` accepts `host` or `host:port` as a fallback
  to native host/port settings. Port lists/ranges are rejected.
- django-configurations is an optional extra; its importer installs before Django setup.

## Compatible pytest fallback and discovery

Search upward from the declaring conftest directory. The nearest supported configuration
directory wins; unrelated pyproject files are skipped, but empty supported tables/INI
files stop the search. In that directory native defaults overlay one pytest fallback:
`pytest.ini`, `.pytest.ini`, native `[tool.pytest]`, then `[tool.pytest.ini_options]`.

Compatible keys are `DJANGO_SETTINGS_MODULE`, `DJANGO_CONFIGURATION`,
`django_find_project`, `django_debug_mode`, and `FAIL_INVALID_TEMPLATE_VARS`. Boolean
fallback strings are parsed explicitly. `setup.cfg`, `tox.ini`, and `pytest.toml` are
not read, and `addopts` is not forwarded. Full user-facing configuration and alias
precedence are in the [configuration reference](../../site-docs/reference/configuration.md).

## `find_project`

When true, walk up from the same start directory looking for `manage.py`; insert its
directory at `sys.path[0]` so the settings module is importable. Same semantics as
pytest-django's `django_find_project`.

## When Django is set up

Settings resolution, `find_project`, and `django.setup()` run at fixture-module import
time. rustest imports `rustest_fixtures` modules right after the declaring conftest and
before any test module, which is the only point early enough: test modules import models
at collection. `setup_test_environment(debug=...)` runs in the session autouse fixture.
`debug_mode = "keep"` passes `debug=None`.

## Failure behaviour

- **Settings unresolvable** (no `DJANGO_SETTINGS_MODULE` in any channel): Django is not set
  up and the run continues. Non-Django tests pass. Django-dependent fixtures
  report the missing settings configuration.
- **Invalid configuration** (unknown key in `[tool.rustest-django]`, invalid debug-mode
  value, unparsable TOML or env boolean, settings module that fails to import): fail fast.
  The error is captured at import time (rustest swallows import-time exceptions from
  fixture modules), then re-raised from the session autouse fixture so every test fails
  with the same message. Native boolean/string/port types are validated.
- Configuration and bootstrap messages use the implemented `rustest-django: ` prefix.
  Accepted keys or values are included for supported validation failures; bootstrap
  errors retain their original cause without printing a duplicate import-time traceback.
