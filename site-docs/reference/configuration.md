---
id: 20260916090400
title: Configuration
tags: [reference]
---

# Configuration

Every setting can be given three ways, in this precedence order (highest wins):

1. An environment variable.
2. A key under `[tool.rustest-django]` in `pyproject.toml`.
3. A pytest-compatible fallback under `[tool.pytest.ini_options]`, for two keys only
   (`settings_module`, `find_project`) -- useful if you're migrating a project that
   already has a `pytest.ini`-style config and don't want to duplicate it.

```toml
# pyproject.toml
[tool.rustest-django]
settings_module = "myproject.settings"
reuse_db = true
migrations = false
```

## Keys

| Key | Env var | Default | Meaning |
|---|---|---|---|
| `settings_module` | `DJANGO_SETTINGS_MODULE` | none | Dotted path to your Django settings module. Falls back to `[tool.pytest.ini_options] DJANGO_SETTINGS_MODULE` if unset. |
| `reuse_db` | `RUSTEST_DJANGO_REUSE_DB` | `false` | Reuse an existing test database between runs instead of recreating it. Forced to `false` if `create_db` is `true`. |
| — | `RUSTEST_DJANGO_CREATE_DB` | `false` | Force-recreate the test database even if `reuse_db` would otherwise reuse it. Env-var only, no `pyproject.toml` key. |
| `migrations` | `RUSTEST_DJANGO_MIGRATIONS` | `true` | Run Django migrations when building the test database. Set `false` to build the schema directly from models instead (faster, but skips migration correctness checks). |
| `find_project` | `RUSTEST_DJANGO_FIND_PROJECT` | `true` | Search parent directories for a `manage.py` and add its directory to `sys.path`, so `myproject.settings` resolves without extra path configuration. Falls back to `[tool.pytest.ini_options] django_find_project` if unset. |
| `debug_mode` | `RUSTEST_DJANGO_DEBUG_MODE` | `"false"` | Value applied to Django's `DEBUG` setting for the duration of the test run. |

## Boolean values

Boolean env vars accept `1`/`true`/`yes`/`on` or `0`/`false`/`no`/`off` (case-insensitive).
Anything else fails fast with a `rustest-django: ...` error naming the accepted spellings.

## Invalid configuration

An unknown key under `[tool.rustest-django]`, or an unparsable value, fails immediately at
startup with a `rustest-django: ...` error naming the problem -- config errors never fail
silently or fall back to a guessed default.
