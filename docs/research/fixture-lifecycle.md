# Research: rustest fixture lifecycle for external fixture modules

Resolves [#4](https://github.com/ernestomancebo/rustest-django/issues/4). Part of #1.

Sources: rustest repo `apex-engineers-inc/rustest` at commit `757e0ee27ae55058fa9b84ad57a9dfaa38ac8a93` (version `0.18.0` in `pyproject.toml:7`, dated 2026-07-24 in `CHANGELOG.md:10`), its rendered docs (same files under `docs/`), and the `rustest==0.18.0` wheel from PyPI (used for the experiments, Python 3.12). File:line pointers below refer to that commit. `FIXTURE_SCOPES.md` at the repo root is present but stale: it still lists conftest, yield fixtures and autouse as "planned" (`FIXTURE_SCOPES.md:255`, `:265`, `:277`); the code and the experiments below contradict it, so it is not used as a source of truth here.

## Verdict

1. **Autouse from an external module: yes, at every scope.** A fixture loaded via `rustest_fixtures` is built with `class_name = None`, so `autouse=True` applies to every test in every file that sees the conftest, at function/class/module/session scope. Confirmed by experiment for all four scopes and for `unittest.TestCase` classes too.
2. **Consumer override by name: yes, and it wins for the module's own dependants.** Fixtures are keyed by name in one merged `IndexMap` per test file; the conftest's own fixtures are inserted after the `rustest_fixtures` modules, nested conftests are merged farthest-to-nearest, and the test file's own fixtures last. Dependencies are resolved by name against that merged map, so a `django_db_setup` override in conftest is what the module's `_django_db_helper(django_db_setup)` receives. Caveat: the session cache is keyed by name only, so with *nested* conftests that override differently, the first definition to run wins for the whole session.
3. **`request.getfixturevalue(name)`: yes, native.** It tunnels into the active Rust resolver, goes through the normal caches, scope rules and teardown registration, and works from inside an autouse fixture (pytest-django's `_django_db_marker` pattern). `request.addfinalizer` raises `NotImplementedError`.
4. **Teardown ordering:** LIFO within a scope; function teardowns after each test, class at the end of each class group, module at the end of each file, package on package change, session at the very end. **Setup error after a sibling yield fixture already yielded: the sibling's post-`yield` code does not run** (only `finally:` blocks run, via `GeneratorExit` when the generator is garbage-collected). **Teardown raise: swallowed** — a `Warning: Error during fixture teardown:` line on stderr, the test stays `passed`.
5. **Class scope:** classes named `Test*` (plain) and any `unittest.TestCase` subclass are grouped; the class cache is cleared per class group. For module-level test functions each function is its own group, so a class-scoped fixture is effectively function-scoped there. Plain classes get `setup_method`/`teardown_method`; `unittest.TestCase` gets `setUp`/`tearDown` but **not** `setUpClass`/`tearDownClass`.
6. **Session fixture runs exactly once across all files: yes** (one `FixtureContext` for the whole run; session cache never cleared). Confirmed with two files.
7. **Skip/fail/xfail from a fixture:** `rustest.skip()` → test `skipped`; `rustest.xfail()` → `skipped` with `[XFAIL]` prefix; `rustest.fail()` → `failed`. Detection is a *string match on the formatted traceback* for `rustest.decorators.Skipped` / `pytest.skip.Exception` / a line starting with `Skipped:` or ending with `.Skipped`. **`unittest.SkipTest` is not recognised → `failed`.** There is no distinct "error" outcome for fixture-setup failures; they count as `failed`.
8. **Other per-test hooks: none.** No pluggy hooks (documented as "not planned"). The only per-test hooks are `setup_method`/`teardown_method` on plain test classes and `setUp`/`tearDown` on `unittest.TestCase`, neither of which a fixture module can attach to. Autouse fixtures are the only mechanism available to `rustest_django`.

## How external fixture modules are loaded

- `src/discovery.rs:711-764` — `load_conftest_fixtures`. Reads the conftest module dict; at `736` picks `rustest_fixtures`, falling back to `pytest_plugins` at `740`; then at `753-762` inserts the conftest's *own* `@fixture` functions into the same `IndexMap`, so a same-named conftest fixture replaces the module's (`IndexMap::insert` overwrites).
- `src/discovery.rs:588-659` — `load_pytest_plugins_fixtures` (shared by both keys). Accepts a string or list of strings (`596-605`), temporarily prepends the conftest directory to `sys.path` (`607-614`, removed at `656`), imports each module with `importlib.import_module` (`617-620`), and collects every module-dict entry that is a `types.FunctionType` **and** a fixture (`648`; `is_fixture` at `1851`). Each is built with `build_fixture_from_value(py, &value, &name, None)` (`649`), i.e. `class_name = None`.
- `src/discovery.rs:624-631` — an import failure of a listed module only prints `Warning: Failed to import pytest plugin module '...'` and continues; the fixtures then show up later as `Unknown fixture` errors.
- `src/discovery.rs:1974-2018` — `build_fixture_from_value` extracts scope, generator/async flags, `__rustest_fixture_autouse__` (`1929-1934`), params and `__rustest_fixture_name__` (`1938-1943`). Model: `src/model.rs:119-131` (`autouse` at `127`, `class_name` at `131`).
- `src/discovery.rs:770-811` — `merge_conftest_fixtures`, called per test file (`898`): builtins first (`781-783`), then conftest dirs farthest→nearest (`797-803`), then the test module's own fixtures (`806-809`). This is the override precedence: module `rustest_fixtures` < that conftest's own fixtures < nearer conftests < the test file.
- `rustest_fixtures` is only read from `conftest.py` files (the only caller is `load_conftest_fixtures`); a test module cannot declare it. Since a module's `__dict__` is scanned, fixtures *imported into* the package `__init__` (e.g. `from .fixtures import db`) are collected too, which allows a package layout.
- Docs: `docs/guide/fixtures.md:495-583` ("Loading Fixtures from External Modules"), `docs/advanced/pytest-plugins.md:10-41` (fixture modules are supported; pluggy plugins are not).

## Resolution order per test

- `src/execution.rs:1491-1690` — `execute_test_case`. Creates a `FixtureResolver` (`1516-1537`), installs the `getfixturevalue` guard (`1539`), then resolves in this order: **explicit test parameters first** (`1553-1567`), **then autouse fixtures** (`1569-1578`), then `@mark.usefixtures` (`1580-1587`; `apply_usefixtures_marks` at `2079-2103`). The async-batch path does the same (`889-931`). `CHANGELOG.md:41-42` documents this ordering as intentional. Note this differs from pytest, where autouse fixtures are instantiated before explicitly requested ones of the same scope; in rustest a test that lists `db` explicitly runs `db` *before* the autouse `_django_db_marker` (visible in the experiment log).
- `src/execution.rs:2108-2163` — `resolve_autouse_fixtures`: filters `fixture.autouse` and, for fixtures with a `class_name`, matches the current test's class (`2113-2124`; `(None, _) => true` means module/external autouse fixtures run for every test); sorts widest scope first (`2128`); skips names already present in any cache (`2139-2146`); resolves via `resolve_argument` (`2149`).
- `src/execution.rs:1810-2049` — `resolve_fixture_value`. `request` is special-cased and never cached (`1812-1814`, `create_request_fixture` at `2222-2243`: a fresh `FixtureRequest(param, node_name, nodeid, node_markers)` per requesting fixture). Cache lookup order function→class→module→package→session (`1844-1859`) by a key that is just the fixture name (plus `[idx]` for parametrized fixtures, `1826-1841`). Unknown name → `Unknown fixture '...'` error listing available names (`1862-1875`). Cycle detection (`1886-1891`). Scope validation: a fixture may only depend on equal-or-wider scope, `request` exempt (`1893-1904`, `validate_scope_dependency` at `2062-2073`). Generators are advanced once and stored in the per-scope teardown list (`1959-1987`); the value is stored in the cache matching the fixture's scope (`2024-2046`).

## `request.getfixturevalue` and the rest of `request`

- `python/rustest/compat/pytest.py:439-470` — `FixtureRequest.getfixturevalue`: calls `rustest.rust.getfixturevalue` (`447`), which is `src/lib.rs:80-82` → `src/execution.rs:209-228` `resolve_fixture_for_request`, reading the thread-local resolver stack (`170-172`) pushed by `ResolverActivationGuard` (`175-206`) and calling `resolve_for_request` → `resolve_fixture_value` (`2051-2053`). So a dynamically requested fixture is cached, scope-checked and torn down exactly like an injected one (`CHANGELOG.md:203-205`). The pure-Python fallback (`461`, `python/rustest/fixture_registry.py:54-135`) is only used when no resolver is active and does **not** register teardown (`fixture_registry.py:131`, `# TODO: Store generator for teardown`).
- `python/rustest/compat/pytest.py:375-437` — `FixtureRequest`: `scope` is always `"function"` (`403`); `function`/`cls`/`module` are `None` (`416-418`); `addfinalizer` raises `NotImplementedError` with a "use yield" message (`423-437`). Marker access is covered in [marker-introspection.md](marker-introspection.md).

## Caches, scopes and teardown timing

- `src/execution.rs:251-280` — `FixtureContext` holds `session_cache`, `package_cache`, `module_cache`, `class_cache` and a `TeardownCollector` (`232-247`, one `Vec` per non-function scope). It is created once per run (`376-377`).
- Module loop (`378-551`): on package change, class then package scopes are torn down and cleared (`390-398`); `module_cache` is cleared at the start of each file (`402`); tests are grouped by `class_name` preserving module order (`406-412`); `class_cache` is cleared at the start of each group (`416`); after every execution unit whose test has no class, the class cache is cleared **and class teardowns run** (`479-486`); class teardowns run at the end of each group (`528`); module teardowns at the end of the file (`532-536`); package (`554`) and session (`557`) teardowns after the last file. Fail-fast runs `cleanup_all` (`491`, narrowest→widest, `326-337`).
- Function scope: `function_teardowns` live on the resolver (`1706`) and are finalized right after the test body, whether it raised (`1650-1656`) or not (`1664-1668`).
- `src/execution.rs:2449-2500` — `finalize_generators`: drains the list in reverse (`2455`, LIFO), calls `__next__`/`anext`, ignores `StopIteration`, and for any other exception prints `Warning: Error during fixture teardown: ...` to stderr and continues (`2490-2497`). The test outcome is not affected.
- **Setup-error gap:** the early returns in `execute_test_case` for a failing explicit parameter (`1553-1567`), autouse (`1569-1578`) or usefixtures (`1580-1587`) return *without* calling `finalize_generators` on `function_teardowns`. The `Vec<Py<PyAny>>` is dropped with the resolver, so Python closes the suspended generators (`GeneratorExit`); code placed after `yield` does not run, `finally:` blocks do. Higher-scoped generators are on the context and are torn down at their normal time.
- Ctrl+C: `docs/from-pytest/limitations.md:172-178` says finalization on interrupt is not guaranteed ("Planned").

## Class semantics

- `src/discovery.rs:1236-1250` — a class is a test class if it is a `unittest.TestCase` subclass (any name; `is_test_case_class` at `1417-1429`) or its name starts with `Test` (`is_plain_test_class`, `1412-1414`).
- Plain classes: `discover_plain_class_tests_and_fixtures` (`1548-1709`). `@fixture` methods become fixtures with `class_name = Some(cls)` (`1593-1616`) and therefore only autouse for that class (`execution.rs:2117-2123`). Test methods run through a generated wrapper (`create_class_test_runner`, `1789-1830`) that instantiates the class, calls `setup_method` if present (`1802-1804`), the test, then `teardown_method` in `finally` (`1808-1811`) and clears the instance cache (`1812`). Documented at `docs/guide/test-classes.md:337-361`.
- `unittest.TestCase`: each test method becomes `test_class('<name>')()` (`1721-1745`, code at `1731-1732`), i.e. `TestCase.run` with `setUp`/`tearDown`; there is no suite, so `setUpClass`/`tearDownClass` are never invoked (verified below). Fixture arguments cannot be injected into these methods, but module/external autouse fixtures do wrap them (verified below).

## Skip, fail, xfail from a fixture

- `python/rustest/decorators.py` — `Failed` (`945`) raised by `fail()` (`951-984`); `Skipped` (`987`) raised by `skip()` (`993-1023`); `XFailed` (`1026`) raised by `xfail()` (`1032-1058`). `rustest.compat.pytest.skip/fail/xfail` are the same functions (`python/rustest/compat/pytest.py:649-654`).
- `src/execution.rs:589-653` — `run_single_test`: any `Err` from `execute_test_case` (fixture setup or test body alike) is classified by `is_skip_exception` (`656-666`) → `skipped`, `is_xfail_exception` (`689-697`) → `skipped` with `[XFAIL]`, else `failed` (`632-641`). Both classifiers match *strings in the formatted traceback* (`format_pyerr`, `2314-2336`): `rustest.decorators.Skipped`, `pytest.skip.Exception`, or a line starting with `Skipped:` / ending with `.Skipped`. `unittest.case.SkipTest` matches none of these. `@mark.xfail` post-processing is `apply_xfail` (`747-798`).
- The run report has only `passed`/`failed`/`skipped` for tests; `errors` counts collection errors (`--llm` summary in the experiment shows `"errors":0` with three fixture failures).

## Hooks

- `docs/from-pytest/limitations.md:30-36` — "No Hook System … Status: Not planned … Alternative: Use fixtures for setup/teardown and conftest.py for sharing." `docs/advanced/pytest-plugins.md:29-36` lists pluggy hooks, entry points and hook wrappers as unsupported. A grep of `src/` and `python/rustest/` finds no `setup_module`/`setup_function`/`pytest_runtest_*` handling; only `setup_method`/`teardown_method` (`src/discovery.rs:1802-1811`) and unittest's own `setUp`/`tearDown`.

## Experiment

`rustest==0.18.0` installed with `uv venv --python 3.12 .venv && uv pip install rustest==0.18.0` into a scratch venv. Three directories; in each, `conftest.py` sits next to the stand-in fixture module (the conftest directory is what rustest puts on `sys.path`).

### 1. Autouse + override + getfixturevalue + scopes

`rd_stub.py` (the stand-in for `rustest_django`):

```python
from rustest import fixture

def log(msg): print(f"[rd] {msg}")

@fixture(scope="session")
def django_db_setup():
    log("django_db_setup(MODULE DEFAULT) setup"); yield "module-default"
    log("django_db_setup(MODULE DEFAULT) teardown")

@fixture(scope="session", autouse=True)
def _auto_session():  log("autouse session setup"); yield; log("autouse session teardown")
@fixture(scope="module", autouse=True)
def _auto_module():   log("autouse module setup");  yield; log("autouse module teardown")
@fixture(scope="class", autouse=True)
def _auto_class():    log("autouse class setup");   yield; log("autouse class teardown")

@fixture(autouse=True)
def _django_db_marker(request):
    """pytest-django's pattern: autouse + dynamic activation via getfixturevalue."""
    log(f"autouse function setup for {request.node.name}")
    if request.node.get_closest_marker("django_db") is not None:
        helper = request.getfixturevalue("_django_db_helper")
        log(f"  marker present -> getfixturevalue('_django_db_helper') = {helper!r}")
    yield
    log(f"autouse function teardown for {request.node.name}")

@fixture
def _django_db_helper(django_db_setup):
    log(f"_django_db_helper setup (django_db_setup={django_db_setup!r})")
    yield f"helper({django_db_setup})"
    log("_django_db_helper teardown")

@fixture
def db(_django_db_helper):
    log("db setup"); yield _django_db_helper; log("db teardown")
```

`conftest.py`:

```python
from rustest import fixture
rustest_fixtures = ["rd_stub"]

@fixture(scope="session")
def django_db_setup():
    print("[conftest] OVERRIDE django_db_setup setup")
    yield "conftest-override"
    print("[conftest] OVERRIDE django_db_setup teardown")
```

`tests/test_a.py`:

```python
from rustest import mark

def test_plain_unmarked():
    print("[test] test_plain_unmarked body")

@mark.django_db
def test_marked_no_arg(request):
    print("[test] test_marked_no_arg body")
    assert request.getfixturevalue("_django_db_helper") == "helper(conftest-override)"

def test_explicit_db(db, request):
    print(f"[test] test_explicit_db body db={db!r}")
    assert db == "helper(conftest-override)"
    assert request.getfixturevalue("db") is db
```

`tests/test_b.py`:

```python
import unittest
from rustest import mark

class TestGroup:
    def test_one(self):
        print("[test] TestGroup.test_one body")
    @mark.django_db
    def test_two(self, db):
        print(f"[test] TestGroup.test_two body db={db!r}")
        assert db == "helper(conftest-override)"

class TestOther:
    def test_three(self):
        print("[test] TestOther.test_three body")

def test_after_classes():
    print("[test] test_after_classes body")

class TestUnit(unittest.TestCase):
    def test_unittest_style(self):
        print("[test] TestUnit.test_unittest_style body")
```

`python -m rustest --no-capture --color never tests` → `8 passed` (rustest ran `test_b.py` before `test_a.py`). Output:

```
[rd] autouse session setup
[rd] autouse module setup
[rd] autouse class setup
[rd] autouse function setup for TestGroup::test_one
[test] TestGroup.test_one body
[rd] autouse function teardown for TestGroup::test_one
[conftest] OVERRIDE django_db_setup setup
[rd] _django_db_helper setup (django_db_setup='conftest-override')
[rd] db setup
[rd] autouse function setup for TestGroup::test_two
[rd]   marker present -> getfixturevalue('_django_db_helper') = 'helper(conftest-override)'
[test] TestGroup.test_two body db='helper(conftest-override)'
[rd] autouse function teardown for TestGroup::test_two
[rd] db teardown
[rd] _django_db_helper teardown
[rd] autouse class teardown
[rd] autouse class setup
[rd] autouse function setup for TestOther::test_three
[test] TestOther.test_three body
[rd] autouse function teardown for TestOther::test_three
[rd] autouse class teardown
[rd] autouse class setup
[rd] autouse function setup for test_after_classes
[test] test_after_classes body
[rd] autouse function teardown for test_after_classes
[rd] autouse class teardown
[rd] autouse class setup
[rd] autouse function setup for TestUnit::test_unittest_style
[test] TestUnit.test_unittest_style body
[rd] autouse function teardown for TestUnit::test_unittest_style
[rd] autouse class teardown
[rd] autouse module teardown
[rd] autouse module setup
[rd] autouse class setup
[rd] autouse function setup for test_plain_unmarked
[test] test_plain_unmarked body
[rd] autouse function teardown for test_plain_unmarked
[rd] autouse class teardown
[rd] autouse class setup
[rd] autouse function setup for test_marked_no_arg
[rd] _django_db_helper setup (django_db_setup='conftest-override')
[rd]   marker present -> getfixturevalue('_django_db_helper') = 'helper(conftest-override)'
[test] test_marked_no_arg body
[rd] autouse function teardown for test_marked_no_arg
[rd] _django_db_helper teardown
[rd] autouse class teardown
[rd] _django_db_helper setup (django_db_setup='conftest-override')
[rd] db setup
[rd] autouse class setup
[rd] autouse function setup for test_explicit_db
[test] test_explicit_db body db='helper(conftest-override)'
[rd] autouse function teardown for test_explicit_db
[rd] db teardown
[rd] _django_db_helper teardown
[rd] autouse class teardown
[rd] autouse module teardown
[conftest] OVERRIDE django_db_setup teardown
[rd] autouse session teardown
```

What the log shows: session autouse once for the run; module autouse once per file; class autouse once per `Test*` group *and once per module-level function*; the module's default `django_db_setup` never ran (override won) and the module's own `_django_db_helper` received `'conftest-override'`; `getfixturevalue` from inside the autouse fixture created `_django_db_helper` with teardown registered (`_django_db_helper teardown` appears after the function autouse teardown) and returned the cached object when called again from the test; explicit `db` was set up *before* the autouse function fixture and torn down after it (LIFO); autouse fixtures also wrap the `unittest.TestCase` method.

`tests/test_c.py` (same directory) with a `unittest.TestCase` defining `setUpClass`/`tearDownClass`/`setUp`/`tearDown` and a plain `TestPlainHooks` with `setup_method`/`teardown_method`, run with `--no-capture` (autouse lines filtered):

```
[unit] setUp
[unit] test_one body
[unit] tearDown
[unit] setUp
[unit] test_two body
[unit] tearDown
[plain] setup_method
[plain] test_one body
[plain] teardown_method
```

`setUpClass`/`tearDownClass` did not run.

### 2. Skip / fail / xfail / setup and teardown errors

`rd_fail.py` (loaded via `rustest_fixtures = ["rd_fail"]`):

```python
import unittest
from rustest import fixture, skip, fail, xfail
from rustest.compat import pytest as compat_pytest

@fixture
def skip_rustest():  skip("skipped from fixture")
@fixture
def skip_compat():   compat_pytest.skip("skipped via rustest.compat.pytest.skip")
@fixture
def skip_unittest(): raise unittest.SkipTest("unittest SkipTest from fixture")
@fixture
def fail_rustest():  fail("failed from fixture")
@fixture
def xfail_rustest(): xfail("xfailed from fixture")

@fixture
def outer_yield():
    print("[rd] outer_yield setup")
    try:
        yield "outer"
        print("[rd] outer_yield teardown (plain code after yield)")
    finally:
        print("[rd] outer_yield finally-block ran")

@fixture
def inner_raises(outer_yield):
    print("[rd] inner_raises setup -> raising RuntimeError")
    raise RuntimeError("setup boom")

@fixture
def teardown_raiser():
    print("[rd] teardown_raiser setup"); yield "x"
    print("[rd] teardown_raiser teardown -> raising"); raise RuntimeError("function teardown boom")

@fixture(scope="module")
def module_teardown_raiser():
    print("[rd] module_teardown_raiser setup"); yield "m"
    print("[rd] module_teardown_raiser teardown -> raising"); raise RuntimeError("module teardown boom")
```

`tests/test_outcomes.py` has one test per fixture (`test_skip_rustest(skip_rustest)`, … each with `raise AssertionError("body must not run")` for the skip/fail/xfail/setup cases), plus `test_teardown_error(teardown_raiser)`, `test_module_raiser(module_teardown_raiser)` and `test_last()` which only print.

`python -m rustest --no-capture --color never tests` → exit code 1, `3 passed, 3 failed, 3 skipped`; stderr shows `Warning: Error during fixture teardown: RuntimeError: function teardown boom` and `... module teardown boom`. Per-test status via `rustest.run(paths=["tests"])`:

```
skipped  test_skip_rustest      skipped from fixture
skipped  test_skip_compat       skipped via rustest.compat.pytest.skip
failed   test_skip_unittest     unittest.case.SkipTest: unittest SkipTest from fixture
failed   test_fail              rustest.decorators.Failed: failed from fixture
skipped  test_xfail             [XFAIL] xfailed from fixture
failed   test_setup_error       RuntimeError: setup boom
passed   test_teardown_error
passed   test_module_raiser
passed   test_last
```

Print order for the setup-error and teardown cases:

```
[rd] outer_yield setup
[rd] inner_raises setup -> raising RuntimeError
[rd] outer_yield finally-block ran            <- plain after-yield line never printed
[rd] teardown_raiser setup
[test] test_teardown_error body ran
[rd] teardown_raiser teardown -> raising      <- test still "passed"
[rd] module_teardown_raiser setup
[test] test_module_raiser body ran
[test] test_last body ran
[rd] module_teardown_raiser teardown -> raising
```

`--llm` summary line: `{"t":"summary","passed":3,"failed":3,"skipped":3,"errors":0,...}` — fixture failures are `failed`, not `errors`.

### 3. Nested-conftest override vs the name-keyed session cache

Root `conftest.py` = `rustest_fixtures = ["rd_stub"]`; `tests/app1/conftest.py` overrides `django_db_setup` (yields `"app1-override"`); `tests/app1/test_app1.py` and `tests/app2/test_app2.py` each have one test taking `db`.

`python -m rustest --no-capture tests/app1 tests/app2`:

```
[app1/conftest] OVERRIDE django_db_setup setup
[rd] _django_db_helper setup (django_db_setup='app1-override')
[test] app1 sees db='helper(app1-override)'
[rd] _django_db_helper setup (django_db_setup='app1-override')
[test] app2 sees db='helper(app1-override)'
[app1/conftest] OVERRIDE django_db_setup teardown
```

`python -m rustest --no-capture tests/app2 tests/app1`:

```
[rd] django_db_setup(MODULE DEFAULT) setup
[test] app2 sees db='helper(module-default)'
[test] app1 sees db='helper(module-default)'
[rd] django_db_setup(MODULE DEFAULT) teardown
```

The session cache is keyed by the name `django_db_setup` (`src/execution.rs:1844-1859`, `2024-2027`), so whichever definition is resolved first serves every later file, even ones whose merged fixture map holds a different callable. pytest would give each directory its own session-scoped instance of the overriding definition.

## Consequences for the port

1. **The whole pytest-django fixture layer can be shipped as a fixture module.** `rustest_fixtures = ["rustest_django"]` in the consumer's conftest loads every `@fixture` function in the package's `__dict__`, including autouse ones at every scope; `request.getfixturevalue` and `request.node.get_closest_marker` make the `_django_db_marker` autouse pattern portable as-is. Keep the package import side-effect free and cheap: an import error is downgraded to a warning (`src/discovery.rs:624-631`) and surfaces later as `Unknown fixture`.
2. **`django_db_setup` override works by name**, in the same conftest that declares `rustest_fixtures` or in any nearer conftest/test file. Document the nested-conftest caveat: session fixtures are cached by name for the run, so differing overrides in sibling directories are first-come. Prefer a single override at the conftest that declares `rustest_fixtures`.
3. **Ordering differs from pytest:** explicitly requested fixtures resolve before autouse ones (`src/execution.rs:1553-1571`). Any autouse fixture in `rustest_django` that must run *before* `db`/`transactional_db` (e.g. blocker unblocking, settings, mailbox reset, URLconf) must be reached from those fixtures' own dependency chains, not rely on autouse-first ordering. Conversely, teardown is LIFO of setup, so autouse teardowns run before `db` teardown when `db` was requested explicitly.
4. **`unittest.SkipTest` is a failure.** Django's `skipUnlessDBFeature`/`skipIfDBFeature` and anything else raising `SkipTest` from a fixture will fail the test. `rustest_django` must raise `rustest.Skipped` (via `rustest.skip`) itself, and should translate `SkipTest` where it wraps Django helpers. Never rely on `pytest.skip` from the real pytest: the classifier only knows `pytest.skip.Exception` by string.
5. **Do not depend on post-`yield` teardown running when a *later* fixture's setup fails** (`src/execution.rs:1553-1587` return without finalizing). Transaction rollback / connection cleanup in `db`-style fixtures must sit in `try/finally` around the `yield` (the `finally` runs on generator close), otherwise a failing sibling fixture leaves the test database dirty. Also, a teardown exception is only a stderr warning; pytest would report a teardown ERROR. Log loudly in teardown.
6. **No `addfinalizer`, no hooks.** `request.addfinalizer` raises `NotImplementedError`; there is no `pytest_runtest_setup`/`pytest_collection_modifyitems`. Everything pytest-django does in hooks (settings configuration, blocker setup, `--reuse-db`/`--create-db` options, `setup_databases` at session start) has to move into a session-scoped autouse fixture, and CLI options have no equivalent: `request.config.getoption` (`python/rustest/compat/pytest.py:289-302`) reads an options dict that the engine never populates (`create_request_fixture` at `src/execution.rs:2222-2243` passes no `config_options`), so it always returns the default. `--reuse-db`/`--create-db` style switches will have to come from environment variables or settings.
7. **Class scope:** `scope="class"` fixtures from the module behave as function-scoped for module-level tests (class cache cleared after each plain function, `src/execution.rs:479-486`). Django's `TestCase`-style `setUpClass`/`setUpTestData` do not run under rustest's unittest runner (`src/discovery.rs:1731-1732`), so a `rustest_django` cannot piggy-back on them; class-level DB setup must be a class-scoped fixture. Class-level `@mark.django_db` is separately unsupported (see marker-introspection.md).
8. **Session fixtures run once per process**; `--reuse-db`-style state can live in a session-scoped yield fixture, torn down at `src/execution.rs:557`, but not on Ctrl+C (`docs/from-pytest/limitations.md:172-178`).
