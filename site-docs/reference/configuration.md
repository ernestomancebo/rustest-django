# Configuration

Most settings can be given as environment variables or project configuration. The
precedence order is:

1. An environment variable.
2. A key under `[tool.rustest-django]` in `pyproject.toml`.
3. A pytest-compatible fallback under `[tool.pytest.ini_options]`, for three keys only
   (`settings_module`, `find_project`, `debug_mode`) -- useful if your project already
   has pytest configuration in `pyproject.toml` and you don't want to duplicate it.

`RUSTEST_DJANGO_CREATE_DB` is environment-only. The fallback names are
`DJANGO_SETTINGS_MODULE`, `django_find_project`, and `django_debug_mode` in
`pyproject.toml`; rustest-django does not read `pytest.ini`, `setup.cfg`, or `tox.ini`.

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
| `debug_mode` | `RUSTEST_DJANGO_DEBUG_MODE` | `"false"` | One of `"true"`, `"false"`, `"keep"` -- see below. |

## Boolean values

The boolean environment variables accept `1`/`true`/`yes`/`on` or
`0`/`false`/`no`/`off` (case-insensitive). Invalid environment values raise a
`rustest-django: ...` error naming the accepted spellings.

In TOML, write `reuse_db`, `migrations`, and `find_project` as actual booleans
(`true` or `false`), without quotes. These keys currently use Python truthiness
rather than strict type validation: `migrations = "false"` enables migrations.
Rejecting wrong TOML types remains a validation follow-up.

## `debug_mode` values

Unlike the boolean keys above, `debug_mode` is a three-valued string, not a boolean --
writing it as a TOML boolean (`debug_mode = true`) fails fast rather than being
silently misinterpreted:

- `"true"` -- force Django's `DEBUG` setting on for the duration of the test run.
- `"false"` (default) -- force it off.
- `"keep"` -- leave `DEBUG` as your settings module set it.

Case-insensitive; any other value fails fast with a `rustest-django: ...` error naming
the three accepted values.

## Invalid configuration

Unknown keys under `[tool.rustest-django]`, invalid `debug_mode` values, unparsable TOML,
and invalid boolean environment values raise a `rustest-django: ...` error at startup.
TOML boolean keys have the type-validation limitation described above.
