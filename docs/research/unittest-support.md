# Research: does rustest collect and run `unittest.TestCase` / Django `TestCase` classes?

Resolves [#5](https://github.com/ernestomancebo/rustest-django/issues/5). Part of #1.

Sources: rustest repo `apex-engineers-inc/rustest` at commit `757e0ee27ae55058fa9b84ad57a9dfaa38ac8a93` (version `0.18.0` in `pyproject.toml:7` and `Cargo.toml:3`), the `rustest==0.18.0` wheel from PyPI (used for the experiment, with `django==6.1.1` on CPython 3.12.10), CPython's `Lib/unittest/case.py` (3.12.10) and Django's `django/test/testcases.py` (6.1.1). File:line pointers below refer to those exact versions. The `docs/` tree in the rustest repo is the source of https://apex-engineers-inc.github.io/rustest/; `grep -rni unittest docs/` finds no page that documents `unittest.TestCase` collection (only two mentions of "unittest discovery" in IDE tips and `unittest.mock.patch` in `docs/advanced/pytest-compat.md:48`).

## Verdict

**Partial, and unsafe.** rustest *collects* every `unittest.TestCase` subclass (regardless of class name) and, for each `test*` attribute, *executes* `Class('test_name')()`. That is `TestCase.run(result=None)`, which in CPython creates a throwaway `TestResult`, records every assertion failure, error, skip and expected failure into it, and returns normally. rustest discards the return value, so **every collected `TestCase` method is reported as passed** unless something escapes unittest's own exception handling.

Concretely, in `rustest==0.18.0`:

| Feature | Works? | Notes |
|---|---|---|
| Collection of `unittest.TestCase` subclasses | yes | Any name; `is_test_case_class` is checked before the `Test*` prefix rule |
| `setUp` / `tearDown` per test | yes (called) | Run by `unittest.TestCase.run` |
| `addCleanup` | yes (called) | Via `doCleanups()` inside `run` |
| `self.assert*` failures reported as failures | **no** | Swallowed into a `TestResult`; reported as passed |
| Uncaught exception in test body reported as error | **no** | Same |
| `@unittest.skip` / `self.skipTest()` reported as skipped | **no** | Body is correctly *not* run, but the test is reported as passed |
| `@unittest.expectedFailure`, `subTest` | **no** | Outcome swallowed; reported as passed |
| `setUpClass` / `tearDownClass` | **no** | Never called: those are `TestSuite` responsibilities, and rustest never builds a suite |
| `setUpModule` / `tearDownModule` | **no** | Same reason |
| rustest fixtures injected as method arguments (`request`, `db`, ...) | **no** | `parameters` is hard-coded empty; a method with an extra argument raises `TypeError` inside unittest and is reported as passed |
| Autouse fixtures (module/conftest-level) | yes | They run around each `TestCase` method like any other test |
| Class-scoped autouse fixtures declared *on* the TestCase | no | The unittest path does not scan the class for fixtures |
| `@mark.*` on TestCase methods, `-m`, `@mark.usefixtures`, `@rustest.skip` | **no** | `marks` and `skip_reason` are hard-coded empty/None |
| `setup_method` / `teardown_method` on a TestCase | no | Only the *plain* class runner calls them |
| `--pytest-compat` | no effect | The flag never reaches the unittest path |

For Django:

| Feature | Works? | Notes |
|---|---|---|
| `SimpleTestCase.__call__` -> `_pre_setup` / `_post_teardown` | yes | Django overrides `__call__`, so `self.client`, `mail.outbox`, and per-test DB atomics are set up and torn down |
| Per-test rollback in `django.test.TestCase` | yes | `_fixture_setup` enters per-test atomics; `_fixture_teardown` rolls them back. The experiment confirms a row created in one test is gone in the next |
| `setUpTestData` | **no** | Called only from `TestCase.setUpClass`, which rustest never calls; `cls.<attr>` set there is missing on `self` |
| Class-level atomic (`cls_atomics`) | no | Same reason |
| `fixtures = [...]` (loaddata) | no (on sqlite) | With savepoint support, loaddata runs only in `setUpClass` |
| `databases` class attribute / `DatabaseOperationForbidden` for `SimpleTestCase` | **no** | Guards are installed by `SimpleTestCase.setUpClass._add_databases_failures`, never called; a `SimpleTestCase` can freely hit the DB |
| `TestCase` assertion failures reported | **no** | Same swallow as plain unittest |
| `_pre_setup` raising | reported as failed, wrong message | Django calls `result.addError(...)` on `None` -> `AttributeError: 'NoneType' object has no attribute 'addError'`, which escapes and rustest reports a failure with that traceback |
| Test database creation / teardown (`setup_databases`) | not attempted | Nothing in rustest knows about Django; the experiment created the schema from a conftest autouse fixture |

## How rustest handles TestCase classes

### Discovery: `unittest.TestCase` subclasses get their own path

- `src/discovery.rs:1237-1256` — inside `inspect_module`, for each class in the module dict: `if is_test_case_class(py, &value)` -> `discover_unittest_class_tests(...)`; `else if is_plain_test_class(&name)` -> `discover_plain_class_tests_and_fixtures(...)`. The unittest check comes first, so a class named `TestFoo(TestCase)` still takes the unittest path, and a class named `FooTests(TestCase)` (no `Test` prefix) is collected too.
- `src/discovery.rs:1417-1429` — `is_test_case_class` is `issubclass(cls, unittest.TestCase)`.
- `src/discovery.rs:1432-1479` — `discover_unittest_class_tests`: iterates `inspect.getmembers(cls)` (so alphabetical order, inherited members included), takes every callable whose name starts with `test`, and builds a `TestCase` struct with:
  - `callable: create_unittest_method_runner(py, cls, &name)` (1456)
  - `parameters: Vec::new()` (1463) — no fixture arguments will ever be resolved
  - `skip_reason: None` (1465) — `@rustest.skip` / `__rustest_skip__` is not consulted
  - `marks: Vec::new()` (1466) — `collect_marks` is never called, so `@mark.django_db`, `@mark.usefixtures`, `-m` selection all see nothing
  - `has_patches: false` (1470)
  - `class_name: Some(class_name)` (1467), `display_name = "Class::method"` (1453)
- Contrast with the plain-class path `src/discovery.rs:1553-1700`, which extracts parameters (fixtures), marks (`1650`), class-level parametrize, class fixture methods, and `setup_method`/`teardown_method` wrappers (`1793-1816`). None of that is applied to `TestCase` subclasses.
- The `pytest_compat` flag is passed to `discover_plain_class_tests_and_fixtures` (`1250`) but **not** to `discover_unittest_class_tests` (`1240`). In `inspect_module` the flag only affects `check_for_patch_decorator` (`1184`, `1637`, `2042-2050`) and pytest-fixture detection (`1263`); at the top level it injects the `pytest` shim into `sys.modules` (`38-51`, `351-353`), controls markdown code-block tests (`358`) and conftest fixture loading (`378`). Nothing about unittest changes with `--pytest-compat`.

### Execution: `Class('name')()` with no `TestResult`

- `src/discovery.rs:1721-1750` — `create_unittest_method_runner` compiles this Python wrapper:

  ```python
  def run_test():
      test_instance = test_class('<method_name>')
      test_instance()
  ```

  The comment at 1727 says "This will properly invoke setUp, the test method, and tearDown". It does, but the return value of `test_instance()` is discarded.
- `src/execution.rs:1553-1568` — the sync path resolves `test_case.parameters` (empty here), then `resolve_autouse_fixtures()` (1570) and `apply_usefixtures_marks()` (1578, no-op since marks are empty), then calls the callable with no args (`1588-1600`). A test is failed only if the callable raises. The async batch path (`src/execution.rs:887-960`) is the same shape.
- `src/execution.rs:2108-2126` — autouse fixtures with `class_name == None` (module/conftest level) match every test, including `TestCase` methods; this is why the autouse probe in the experiment ran.

### CPython: `TestCase.__call__` swallows outcomes

- `unittest/case.py:689-690` — `__call__` is `return self.run(*args, **kwds)`.
- `unittest/case.py:599-601` — `run(self, result=None)`: `if result is None: result = self.defaultTestResult()`.
- `unittest/case.py:612-617` — `@unittest.skip` / `skipTest` short-circuit: `_addSkip(result, ...)`; `return result`. No exception leaves `run`.
- `unittest/case.py:629-638` — `setUp`, the test method and `tearDown` each run inside `outcome.testPartExecutor(self)`; `doCleanups()` at 638.
- `unittest/case.py:54-83` — `testPartExecutor` catches `SkipTest` (61-63) and *every other exception except `KeyboardInterrupt`* (68-75), recording them via `_addSkip` / `_addError` on the result. Nothing is re-raised.
- `unittest/case.py:692-706` — `debug()` is the variant that "Run[s] the test without collecting errors in a TestResult" and re-raises; rustest does not use it.
- `setUpClass` / `tearDownClass` are invoked by `unittest.suite.TestSuite._handleClassSetUp` / `_tearDownPreviousClass`, i.e. only when a suite runs the tests. `TestCase.run` never calls them.

### Django: what `__call__` still does, and what needs `setUpClass`

- `django/test/testcases.py:308-314` — `SimpleTestCase.__call__(self, result=None)` -> `self._setup_and_call(result)`.
- `testcases.py:338-378` — `_setup_and_call`: unless skipped, runs `self._pre_setup()` (361), then `super().__call__(result)` (372), then `self._post_teardown()` (375). Exceptions from the hooks go to `result.addError(self, sys.exc_info())` (364, 376). With `result=None` that line raises `AttributeError` — the *only* way a Django `TestCase` reports a failure to rustest, and with a misleading traceback.
- `testcases.py:380-388` — `SimpleTestCase._pre_setup`: creates `cls.client`, `cls.async_client`, clears `mail.outbox`.
- `testcases.py:1146-1160` — `TransactionTestCase._pre_setup`: `available_apps`, then `_fixture_setup`.
- `testcases.py:1472-1490` — `TestCase._fixture_setup`: `cls.atomics = cls._enter_atomics()` (1481) per test; `loaddata` / `setUpTestData` only when the DB lacks savepoints (1482-1490).
- `testcases.py:1235-1258` — `TransactionTestCase._post_teardown` -> `_fixture_teardown`; `testcases.py:1492-1500` — `TestCase._fixture_teardown` -> `_rollback_atomics(self.atomics)`. This is the per-test rollback that the experiment shows working.
- `testcases.py:214-221` — `SimpleTestCase.setUpClass` calls `cls._add_databases_failures()` (220), which installs the `DatabaseOperationForbidden` wrappers for aliases not in `cls.databases` (245-270). Never called under rustest, so `databases` has no effect.
- `testcases.py:1419-1449` — `TestCase.setUpClass`: `cls.cls_atomics = cls._enter_atomics()` (1426), `loaddata` for `cls.fixtures` (1428-1438), `cls.setUpTestData()` (1442). `tearDownClass` (1451-1459) rolls `cls_atomics` back. None of this runs under rustest.

## Experiment

Environment (exact commands, run in a scratch directory):

```
uv venv -q --python 3.12 .venv
uv pip install -q --python .venv/bin/python rustest==0.18.0 django
# -> Python 3.12.10, django 6.1.1
```

### 1. Plain `unittest.TestCase`

`plain/test_plain_unittest.py`:

```python
import unittest
from rustest import fixture

@fixture(autouse=True)
def autouse_probe():
    print("[autouse fixture] setup")
    yield
    print("[autouse fixture] teardown")

class PlainCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls): print("[setUpClass]")
    @classmethod
    def tearDownClass(cls): print("[tearDownClass]")
    def setUp(self): print(f"[setUp] {self._testMethodName}")
    def tearDown(self): print(f"[tearDown] {self._testMethodName}")

    def test_01_passes(self):
        print("[test_01_passes] body"); self.assertEqual(1, 1)
    def test_02_assert_fails(self):
        print("[test_02_assert_fails] body"); self.assertEqual(1, 2)
    def test_03_raises(self):
        print("[test_03_raises] body"); raise RuntimeError("boom")
    @unittest.skip("skipped on purpose")
    def test_04_unittest_skip(self):
        print("[test_04_unittest_skip] body SHOULD NOT PRINT")
    def test_05_skiptest(self):
        self.skipTest("via self.skipTest")
    def test_06_wants_request(self, request):
        print("[test_06_wants_request] got", request)
    def test_07_addcleanup(self):
        self.addCleanup(lambda: print("[addCleanup ran]"))
    @unittest.expectedFailure
    def test_08_expected_failure(self):
        self.assertTrue(False)
    def test_09_subtest(self):
        for i in (1, 2):
            with self.subTest(i=i):
                self.assertEqual(i, 1)

class NotTestPrefixed(unittest.TestCase):
    def test_collected_anyway(self):
        print("[NotTestPrefixed.test_collected_anyway] body")
```

`python -m rustest --no-capture --color never test_plain_unittest.py` -> exit 0, `Collected 10 tests`, **`10 passed`**. Output (trimmed to the first three tests and the tail):

```
[autouse fixture] setup
[setUp] test_01_passes
[test_01_passes] body
[tearDown] test_01_passes
[autouse fixture] teardown
[autouse fixture] setup
[setUp] test_02_assert_fails
[test_02_assert_fails] body
[tearDown] test_02_assert_fails
[autouse fixture] teardown
[autouse fixture] setup
[setUp] test_03_raises
[test_03_raises] body
[tearDown] test_03_raises
[autouse fixture] teardown
[autouse fixture] setup            <- test_04: setUp/body correctly not run (skip honoured internally)
[autouse fixture] teardown
...
[setUp] test_07_addcleanup
[tearDown] test_07_addcleanup
[addCleanup ran]
...
[autouse fixture] setup
[NotTestPrefixed.test_collected_anyway] body
[autouse fixture] teardown
```

`[setUpClass]` and `[tearDownClass]` never appear. `[test_06_wants_request] got ...` never appears (the method raised `TypeError` inside unittest).

`python -m rustest --pytest-compat --no-capture --color never test_plain_unittest.py` -> identical output plus the compatibility banner; still `10 passed`.

Control, `python -m unittest -v test_plain_unittest` -> `Ran 10 tests`, **`FAILED (failures=2, errors=2, skipped=2, expected failures=1)`**, and `[setUpClass]` / `[tearDownClass]` are printed.

Direct demonstration of the swallow, reproducing exactly what rustest's wrapper does:

```
$ python -c "
import test_plain_unittest as m
r = m.PlainCase('test_02_assert_fails')()
print('return type:', type(r).__name__, '| wasSuccessful:', r.wasSuccessful())
print('failures:', r.failures[0][1].strip().splitlines()[-1])
r = m.PlainCase('test_06_wants_request')()
print('errors:', r.errors[0][1].strip().splitlines()[-1])
r = m.PlainCase('test_04_unittest_skip')()
print('skipped:', r.skipped)"
return type: TestResult | wasSuccessful: False
failures: AssertionError: 1 != 2
errors: TypeError: PlainCase.test_06_wants_request() missing 1 required positional argument: 'request'
skipped: [(<test_plain_unittest.PlainCase testMethod=test_04_unittest_skip>, 'skipped on purpose')]
```

### 2. Django `TestCase` / `SimpleTestCase`

`django/settings.py`:

```python
SECRET_KEY = "x"
INSTALLED_APPS = ["myapp"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
```

`django/myapp/models.py`: `class Thing(models.Model): name = models.CharField(max_length=50)` (plus an empty `__init__.py`).

`django/conftest.py`:

```python
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()
from django.core.management import call_command
from rustest import fixture

@fixture(scope="session", autouse=True)
def _django_schema():
    call_command("migrate", run_syncdb=True, verbosity=0)
    print("[conftest] in-memory sqlite schema created")
    yield
```

`django/test_django_testcase.py`:

```python
from django.db import connection
from django.test import SimpleTestCase, TestCase
from myapp.models import Thing

class ThingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        print("[setUpTestData] called")
        cls.seed = Thing.objects.create(name="seed")

    def setUp(self):
        print(f"[setUp] {self._testMethodName} count={Thing.objects.count()} "
              f"cls_atomics={hasattr(type(self), 'cls_atomics')} "
              f"in_atomic_block={connection.in_atomic_block}")

    def test_a_create_row(self):
        Thing.objects.create(name="a")
        print("[test_a_create_row] count after create =", Thing.objects.count())

    def test_b_row_is_gone(self):
        n = Thing.objects.count()
        print("[test_b_row_is_gone] count =", n)
        self.assertEqual(n, 1, "expected only the setUpTestData seed row")

    def test_c_seed_attr(self):
        print("[test_c_seed_attr] self.seed =", getattr(self, "seed", "MISSING"))
        self.assertTrue(hasattr(self, "seed"))

class NoDbTests(SimpleTestCase):
    def test_db_access(self):
        # Under Django's runner this raises DatabaseOperationForbidden.
        print("[SimpleTestCase.test_db_access] count =", Thing.objects.count())
```

`PYTHONPATH=. python -m rustest --no-capture --color never test_django_testcase.py` -> exit 0, `Collected 4 tests`, **`4 passed`**:

```
[conftest] in-memory sqlite schema created
[setUp] test_a_create_row count=0 cls_atomics=False in_atomic_block=True
[test_a_create_row] count after create = 1
[setUp] test_b_row_is_gone count=0 cls_atomics=False in_atomic_block=True
[test_b_row_is_gone] count = 0
[setUp] test_c_seed_attr count=0 cls_atomics=False in_atomic_block=True
[test_c_seed_attr] self.seed = MISSING
[SimpleTestCase.test_db_access] count = 0
```

Reading: `in_atomic_block=True` and `count=0` in `test_b` show the per-test atomic + rollback from `_pre_setup`/`_post_teardown` works. `[setUpTestData] called` never appears, `cls_atomics=False`, `self.seed = MISSING`; `test_c`'s `assertTrue` failed but rustest reports it passed. The `SimpleTestCase` DB query succeeds instead of raising.

`--pytest-compat` run: identical output, `4 passed`.

Control, `PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python -m django test -v 2 test_django_testcase` -> `Ran 4 tests`, **`FAILED (failures=1)`** (the `SimpleTestCase` query raises `DatabaseOperationForbidden: Database queries to 'default' are not allowed in SimpleTestCase subclasses`), with:

```
[setUpTestData] called
[setUp] test_a_create_row count=1 cls_atomics=True in_atomic_block=True
[test_a_create_row] count after create = 2
[setUp] test_b_row_is_gone count=1 cls_atomics=True in_atomic_block=True
[test_b_row_is_gone] count = 1
[setUp] test_c_seed_attr count=1 cls_atomics=True in_atomic_block=True
[test_c_seed_attr] self.seed = Thing object (1)
```

### 3. Two extra probes

`fixtures = ["does_not_exist"]` on a `TestCase` under rustest -> `1 passed`, body runs. On sqlite (savepoints supported) `loaddata` only happens in `setUpClass`, so the missing fixture is never noticed.

A `TestCase` whose `_pre_setup` raises `RuntimeError` under rustest -> `1 failed`, but the reported traceback ends in `testcases.py:364 result.addError(self, sys.exc_info()) AttributeError: 'NoneType' object has no attribute 'addError'` (the original `RuntimeError` is shown above it as the "during handling" cause).

## Consequences for the port

1. **Do not advertise unittest-style Django `TestCase` support on top of rustest 0.18.0 as it stands.** Any `django.test.TestCase` / `SimpleTestCase` file that rustest collects is reported green regardless of what its assertions do. This is worse than "unsupported": it silently masks failures. If rustest-django cannot prevent this, it must at least fail loudly (per CONTEXT.md) — e.g. a conftest-level check that scans collected modules for `unittest.TestCase` subclasses and raises, or documents that such files must be excluded from rustest's paths.
2. The rustest-side fix is small and upstreamable: `src/discovery.rs:1721-1750` should run the instance with a result that re-raises, e.g. `test_instance.debug()` (`unittest/case.py:692-706`, and Django overrides `debug()` at `testcases.py:333-336` to keep `_pre_setup`/`_post_teardown` and re-raise), or pass an explicit `TestResult` and raise from its `failures`/`errors`/`skipped`. Without that, nothing built on top can make `self.assert*` failures visible.
3. Even with outcomes fixed, class-level lifecycle is absent: `setUpClass`/`tearDownClass` (and therefore Django's `setUpTestData`, `cls_atomics`, `fixtures`, `_add_databases_failures`/`databases`) never run because rustest never builds a `TestSuite`. A port that wanted Django `TestCase` semantics would have to invoke `setUpClass`/`tearDownClass` itself around the class's methods (e.g. from a class-keyed session fixture) — but rustest gives `TestCase` methods no fixture parameters, no marks and no class-fixture scanning (`discovery.rs:1463-1466`), so the only hook available is a module/conftest-level autouse fixture, which does not know which class is running (`request.cls` is `None`, see `marker-introspection.md`).
4. What *does* work is the per-test slice driven by Django's own `__call__`: `_pre_setup` (test client, `mail.outbox`, per-test atomic) and `_post_teardown` (rollback, connection close). So a `TestCase` gets real per-test DB isolation once a database exists — but rustest-django still has to create/destroy the test database itself (pytest-django's `django_db_setup`), and there is no marker or fixture on the `TestCase` method to trigger that; a session-scoped autouse fixture is the only lever.
5. `--pytest-compat` is irrelevant to this decision; it changes nothing on the unittest path.
6. Recommendation for the "unittest-style Django TestCase support, in or out" decision: **out** for v1. Support pytest-style tests (functions and plain `Test*` classes, which do get fixtures, marks and `setup_method`) only, refuse or warn on `unittest.TestCase` subclasses, and track an upstream rustest issue for `create_unittest_method_runner` reporting outcomes before revisiting.
