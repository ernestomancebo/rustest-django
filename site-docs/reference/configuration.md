# Configuration

Project defaults live under `[tool.rustest-django]` in `pyproject.toml`.
Environment variables override those defaults. Compatible pytest settings provide
fallbacks for settings discovery, debug mode, project discovery, configuration-class
selection, and strict template checking.

```toml
[tool.rustest-django]
settings_module = "myproject.settings"
reuse_db = true
migrations = false
live_server_host = "localhost"
live_server_port = 0
fail_on_template_vars = true
```

## Discovery and precedence

Search upward from the declaring `conftest.py` directory. The nearest directory with
supported TOML tables or an INI file wins; unrelated `pyproject.toml` files are skipped.
An empty supported table or INI file stops discovery instead of inheriting parent
configuration.

Within that directory, native `[tool.rustest-django]` values coexist with one pytest
fallback source, selected in this order:

1. `pytest.ini` (`[pytest]`).
2. `.pytest.ini` (`[pytest]`).
3. Native pytest TOML settings under `[tool.pytest]`.
4. INI-style pytest settings under `[tool.pytest.ini_options]`.

Value precedence is environment variable, native project key, selected pytest fallback,
then the built-in default. `setup.cfg`, `tox.ini`, and `pytest.toml` are not read.
Pytest `addopts` is not forwarded as rustest command-line arguments.

## Keys

| Key | Environment variable | Default | Meaning |
|---|---|---|---|
| `settings_module` | `DJANGO_SETTINGS_MODULE` | none | Dotted Django settings module. Pytest fallback: `DJANGO_SETTINGS_MODULE`. |
| `configuration` | `DJANGO_CONFIGURATION` | none | django-configurations class; requires the optional extra below. Pytest fallback: `DJANGO_CONFIGURATION`. |
| `reuse_db` | `RUSTEST_DJANGO_REUSE_DB` | `false` | Keep the test database between runs. Cancelled when `create_db` is true. |
| — | `RUSTEST_DJANGO_CREATE_DB` | `false` | Recreate the test database. Environment-only; no TOML key. |
| `migrations` | `RUSTEST_DJANGO_MIGRATIONS` | `true` | Run migrations when creating test databases. False builds schema directly from models. |
| `find_project` | `RUSTEST_DJANGO_FIND_PROJECT` | `true` | Find a parent `manage.py` and add its directory to the import path. Pytest fallback: `django_find_project`. |
| `debug_mode` | `RUSTEST_DJANGO_DEBUG_MODE` | `"false"` | Force Django DEBUG true/false, or leave it unchanged with `"keep"`. Pytest fallback: `django_debug_mode`. |
| `live_server_host` | `RUSTEST_DJANGO_LIVE_SERVER_HOST` | `"localhost"` | Host for the live-server fixture. |
| `live_server_port` | `RUSTEST_DJANGO_LIVE_SERVER_PORT` | `0` | Port from 0 to 65535; 0 asks the operating system for an available port. |
| `fail_on_template_vars` | `RUSTEST_DJANGO_FAIL_ON_TEMPLATE_VARS` | `false` | Reject undefined variables rendered by configured Django template backends. Pytest fallback: `FAIL_INVALID_TEMPLATE_VARS`. |

## Boolean values

Boolean environment variables and pytest fallback values accept
`1`/`true`/`yes`/`on` or `0`/`false`/`no`/`off`, case-insensitively.
Native TOML boolean keys require actual `true` or `false` values: quoted strings and
numbers raise an error instead of being interpreted through truthiness.

The upstream `FAIL_INVALID_TEMPLATE_VARS` environment variable is also accepted.
`RUSTEST_DJANGO_FAIL_ON_TEMPLATE_VARS` takes precedence over that alias; either
environment value overrides project configuration.

Strict template checking is a project policy. Use the
[`ignore_template_errors` marker](markers.md#markignore_template_errors) for per-test
exceptions.

## Debug mode

`debug_mode` accepts the strings `"true"`, `"false"`, and `"keep"`, case-insensitively.
It defaults to `"false"`; `"keep"` preserves the value from Django settings.
A native TOML boolean such as `debug_mode = true` is invalid.

## Live-server address compatibility

`DJANGO_LIVE_TEST_SERVER_ADDRESS` supplies fallback host/port values using `host` or
`host:port`. Port lists and ranges are rejected. Native host/port keys and their
`RUSTEST_DJANGO_*` environment variables override the corresponding address components.
Supplying both components directly bypasses the legacy address entirely.

## django-configurations

Install the optional integration:

```bash
uv add 'rustest-django[configurations]'
```

Then select the settings module and class:

```toml
[tool.rustest-django]
settings_module = "myproject.settings"
configuration = "Test"
```

The importer is installed before Django initializes and before test modules import
models. Missing optional dependencies produce installation guidance.

## Database suffixes

`TOX_PARALLEL_ENV` adds a tox-environment suffix. `RUSTEST_DJANGO_DB_SUFFIX` adds an
explicit worker suffix, falling back to `PYTEST_XDIST_WORKER`. Both can apply, in that
order. These identities come from the process environment and are applied through
[Django database lifecycle fixtures](fixtures.md#database).

## Invalid configuration

Unknown native keys, invalid types, malformed supported configuration, and out-of-range
ports fail at startup. Plugin configuration errors use the `rustest-django: ` prefix.
Rustest may report malformed TOML before loading fixture modules.
