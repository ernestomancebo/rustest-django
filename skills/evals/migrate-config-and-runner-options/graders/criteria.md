---
type: llm
weight: 1
---

PASS when the response supplies native `[tool.rustest-django]` with string
settings_module and configuration, boolean fail_on_template_vars=true, string
live_server_host="127.0.0.1", and integer live_server_port=0, and installs the
rustest-django[configurations] extra.
It gives precedence environment > native TOML > selected pytest fallback > defaults,
so project.ci wins for settings and native strict checking stays true. Unrelated
pyproject files are skipped; an empty supported source at a nearer declaring
conftest directory stops upward discovery and does not inherit root defaults.
It says pytest addopts/plugin flags are not forwarded, maps reuse to reuse_db=true
or RUSTEST_DJANGO_REUSE_DB and no migrations to migrations=false or
RUSTEST_DJANGO_MIGRATIONS=false, and gives TOX_PARALLEL_ENV plus externally supplied
RUSTEST_DJANGO_DB_SUFFIX (or PYTEST_XDIST_WORKER) for suffixes. It distinguishes
function-level urls/app-isolation/template-exemption markers from project defaults.

FAIL if it invents plugin CLI registration/forwarding, promises automatic native
worker identity, treats quoted TOML booleans as valid, reverses precedence, or
inherits root defaults past an empty supported source. Exact prose or table format
is not required.
