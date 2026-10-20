# Agent skills

Two [agent skills](https://github.com/ernestomancebo/rustest-django/tree/main/skills) let
a coding agent such as Claude Code do the migration work and diagnose failures for you.

## Install

Install both with [skills.sh](https://skills.sh), which supports Claude Code and other
agents:

```bash
npx skills add ernestomancebo/rustest-django
```

Ask by skill name so the right one loads.

## `rustest-django-migrate-tests`

Ports a pytest-django suite to rustest-django: the `pytest_django` to `rustest_django`
re-referencing from the [Migration Guide](migration-guide.md), and the rewrite of Django
`TestCase`-family classes (`SimpleTestCase`, `TestCase`, `TransactionTestCase`,
`LiveServerTestCase`) into plain test functions. Use it when porting a project, when a repo
already on rustest-django still has unittest-style Django test classes, or when
rustest-django fails with "unittest-style tests are unsupported".

Try: *"Use `rustest-django-migrate-tests` to migrate these tests to rustest-django."*

## `rustest-django-doctor`

Diagnoses a failing or confusing rustest-django test: a database-access error, a test that
passes when it shouldn't, an unsupported-feature error, or a test that behaves differently
than under pytest-django. It tells you whether the cause is your suite or a known
limitation (see [Unsupported features](reference/unsupported.md)), and it does not silently
"fix" causes that have no fix.

Try: *"Use `rustest-django-doctor` to explain why this test fails under rustest-django."*
