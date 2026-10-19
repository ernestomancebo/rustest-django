---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Use `rustest-django-migrate-tests` for the current plugin. We use django-configurations
and want these defaults in the root pyproject.toml: settings module project.settings,
configuration class Test, strict template variables, and live-server host 127.0.0.1
with a port selected by the OS. Give the TOML and the optional dependency to install.

The root pytest.ini also sets `DJANGO_SETTINGS_MODULE = project.legacy` and
`FAIL_INVALID_TEMPLATE_VARS = false`; CI exports `DJANGO_SETTINGS_MODULE=project.ci`.
Which settings module and strict-template policy win? Tests load the plugin from
root conftest.py. A nested directory has an unrelated pyproject.toml with only a
project table: does that prevent finding the root defaults? If a nested declaring
conftest.py instead has an empty supported `[tool.rustest-django]` table beside it,
does it inherit root defaults?

Can we keep pytest addopts `--reuse-db --nomigrations` and assume rustest forwards
them? Show supported settings/env alternatives, and explain how separate tox/worker
processes get database suffixes. Please distinguish configured defaults from
per-test URL/app/template behavior.
