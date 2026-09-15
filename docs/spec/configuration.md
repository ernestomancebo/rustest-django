# Configuration and settings discovery

Spec section for rustest-django v1. Decided in wayfinder ticket #10.

rustest has no CLI flag registration, no config object reachable from fixtures, and no
rootdir. rustest-django therefore reads its runner options from exactly two channels:

1. **Environment variables**: per-invocation overrides, the replacement for pytest-django's
   CLI flags.
2. **`[tool.rustest-django]` in `pyproject.toml`**: project defaults, the replacement for
   pytest-django's ini options.

Precedence: environment > `[tool.rustest-django]` > `[tool.pytest.ini_options]` fallback >
built-in default.

## Keys

| key | type | default | env twin | pytest-django equivalent |
|---|---|---|---|---|
| `settings_module` | str | none | `DJANGO_SETTINGS_MODULE` | `--ds`, ini `DJANGO_SETTINGS_MODULE` |
| `reuse_db` | bool | `false` | `RUSTEST_DJANGO_REUSE_DB` | `--reuse-db` |
| (env only) | bool | `false` | `RUSTEST_DJANGO_CREATE_DB` | `--create-db` |
| `migrations` | bool | `true` | `RUSTEST_DJANGO_MIGRATIONS` | `--migrations` / `--no-migrations` |
| `find_project` | bool | `true` | `RUSTEST_DJANGO_FIND_PROJECT` | ini `django_find_project` |
| `debug_mode` | `"true"` / `"false"` / `"keep"` | `"false"` | `RUSTEST_DJANGO_DEBUG_MODE` | ini `django_debug_mode` |

- `create_db` has no pyproject key: it is a one-shot action, not a project default. As in
  pytest-django it only cancels `reuse_db`.
- Env booleans accept `1`/`0`, `true`/`false`, `yes`/`no`, `on`/`off`, case-insensitive.
- No `liveserver` key in v1; added by the live_server decision if that feature lands.
- django-configurations (`--dc`, `DJANGO_CONFIGURATION`) is out of scope.

## `[tool.pytest.ini_options]` fallback

When a key is absent from `[tool.rustest-django]`, the pytest-django ini names are read
from `[tool.pytest.ini_options]` in the same file: `DJANGO_SETTINGS_MODULE`,
`django_find_project`, `django_debug_mode`. No notice is printed; a project may run both
runners during migration. `pytest.ini`, `setup.cfg` and `tox.ini` are not read.

## Locating `pyproject.toml`

Start directory: the directory of the `conftest.py` that declared `rustest_fixtures`
(found by scanning `sys.modules` for a module whose `__file__` is a `conftest.py`, falling
back to `sys.path[0]`), then the current working directory. Walk up to the filesystem
root. The first `pyproject.toml` containing either `[tool.rustest-django]` or
`[tool.pytest.ini_options]` wins; a pyproject with neither section is skipped. No file
found means no configuration, not an error.

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
  up and the run continues. Non-Django tests pass. Any Django-dependent fixture fails with
  a message naming the three ways to configure the settings module.
- **Invalid configuration** (unknown key in `[tool.rustest-django]`, wrong TOML type,
  unparsable env boolean, settings module that fails to import): fail fast. The error is
  captured at import time (rustest swallows import-time exceptions from fixture modules),
  printed to stderr, and re-raised from the session autouse fixture so every test fails
  with the same message.
- Exact message shapes are decided with the error UX of unsupported features.
