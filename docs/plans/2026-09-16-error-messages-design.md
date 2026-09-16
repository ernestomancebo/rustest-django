# Error-message shapes for unsupported-feature failures

Resolves GitHub issue #24, deferred in `docs/spec.md`'s "Deferred" section
from the original wayfinder map.

## Problem

Failures for unsupported fixtures/markers, the unittest-style guard, config
validation, and bootstrap failures already explain what's wrong and why in
prose, but with no shared format: no common prefix, inconsistent inclusion
of a suggested fix, and (in `_bootstrap.py`) a redundant stderr traceback
printed on top of the raised exception.

## Message shape

Every message becomes:

```
rustest-django: {what} — {why}. {fix}
```

where `{fix}` is a trailing sentence naming a concrete alternative, omitted
entirely when none exists (rather than a hedge like "no alternative
available").

## Shared helper

A new `src/rustest_django/_errors.py`:

```python
def _message(body: str) -> str:
    return f"rustest-django: {body}"
```

`ConfigError` moves here from `config.py`, so `config.py` and
`_bootstrap.py` can both build on the same module without a circular
import.

No exception *types* change (`RuntimeError`, `ConfigError`, `fail()`), and
no call sites that raise change — this is purely a message-formatting
pass.

## `unsupported.py`

`_unsupported(name)` gains an optional `fix` parameter:

```python
def _unsupported(name: str, fix: str | None = None) -> None:
    body = (
        f"'{name}' is unsupported in rustest-django v1. It exists so a "
        "migrated test naming it fails loudly instead of silently losing "
        "coverage."
    )
    if fix:
        body = f"{body} {fix}"
    raise RuntimeError(_message(body))
```

Per call site:

- `live_server` — no fix. No drop-in alternative exists today (real
  implementation is tracked separately in issue #25).
- `django_db_serialized_rollback` — fix: "If migration-loaded data is
  disappearing after a transactional_db test, try db instead: it wraps the
  test in a transaction rather than truncating tables, so that data
  survives."
- `django_isolated_apps` — no fix. Narrow escape hatch (isolated Apps
  registry for testing custom AppConfigs) with no rustest-django v1
  equivalent.
- `@mark.urls` — fix: "Override settings.ROOT_URLCONF via the settings
  fixture instead."
- `@mark.ignore_template_errors` — no fix. pytest-django's debug-template-
  error suppression, no direct rustest-django equivalent.

## `unittest_guard.py`

Only the prefix changes — the existing message already ends with a fix
("Use plain functions with the db/transactional_db fixtures instead"):

```python
fail(_message(
    f"{test_class.__module__}.{test_class.__qualname__} is a unittest-style "
    "Django TestCase (SimpleTestCase/TestCase/TransactionTestCase/"
    "LiveServerTestCase), which is unsupported in rustest-django v1: rustest "
    "discards its result, so every method would otherwise silently report "
    "as passed. Use plain functions with the db/transactional_db fixtures "
    "instead."
))
```

## `config.py`

Both existing `ConfigError` sites get a fix clause:

- Unknown key(s): append the actual valid set —
  `f"Unknown key(s) in [tool.rustest-django]: {sorted_unknown}. Valid keys: {sorted(_KNOWN_TOOL_KEYS)}."`
- Invalid boolean env var: append the accepted spellings —
  `f"{env_name}={raw!r} is not a valid boolean. Use one of: 1/true/yes/on or 0/false/no/off."`

New: the previously-uncaught `tomllib.TOMLDecodeError` gets wrapped, no fix
clause (the underlying error already pinpoints the syntax problem):

```python
try:
    data = tomllib.loads(pyproject.read_text())
except tomllib.TOMLDecodeError as error:
    raise ConfigError(_message(f"{pyproject} is not valid TOML: {error}")) from error
```

## `_bootstrap.py`

Drop the unconditional `traceback.print_exc(file=sys.stderr)` — `raise ...
from error` already preserves the original traceback for pytest/rustest to
display, so the print was pure duplication:

```python
except Exception as error:
    raise RuntimeError(
        _message(f"failed to configure Django at import time: {error}")
    ) from error
```

## Testing

For each of the 4 files, add/extend a test asserting the raised
exception's `str(...)` (or the `fail()` message, for `unittest_guard.py`)
starts with `"rustest-django: "`, and — where a fix clause is specified
above — contains the expected suggestion substring. For `_bootstrap.py`,
additionally assert stderr no longer contains a duplicate traceback.
Existing tests asserting on old message substrings get updated to the new
wording.
