# Research: rustest async tests and the `--pytest-compat` shim

Resolves [#6](https://github.com/ernestomancebo/rustest-django/issues/6). Part of #1.

Sources: rustest repo `apex-engineers-inc/rustest` at commit `757e0ee27ae55058fa9b84ad57a9dfaa38ac8a93` (version `0.18.0` in `pyproject.toml:7` and `Cargo.toml:3`; `origin/main` HEAD on 2026-09-15), the published docs at <https://apex-engineers-inc.github.io/rustest/> (fetched 2026-09-15; the `advanced/pytest-compat` and `advanced/pytest-plugins` pages match `docs/advanced/*.md` at that commit verbatim), and the `rustest==0.18.0` wheel from PyPI (used for the experiments). File:line pointers below refer to that commit.

## Verdict

### (A) Async

**Async tests are supported natively; `@mark.asyncio` is optional.** rustest decides "async test" by `inspect.iscoroutinefunction` at partition time and by `inspect.iscoroutine(result)` after calling the test; the mark is never consulted for that. The mark's only effects are its `loop_scope` and `timeout` kwargs.

**One event loop per scope, created with `asyncio.new_event_loop()` + `asyncio.set_event_loop()`, never `asyncio.run()`.** The loop a test runs in is chosen by `loop_scope`: explicit `@mark.asyncio(loop_scope=...)` wins; otherwise the *widest scope of any async fixture the test (transitively, including autouse) depends on*; otherwise `function`, floored by `asyncio_default_test_loop_scope` from `pyproject.toml [tool.pytest.ini_options]`. `function` means a fresh loop per test, closed (pending tasks cancelled, `shutdown_asyncgens`, `close()`) right after the test's function-scoped teardowns run.

**Async fixtures (`async def` and `async def` + `yield`) are supported at every scope** (`function`, `class`, `module`, `package`, `session`). Each is run with `loop.run_until_complete` on the loop of `max(fixture.scope, test_loop_scope)`; async-generator teardown is driven by `anext()` on that same loop. So **an async fixture and the test that uses it always share one loop**, and rustest refuses (with a "Loop scope mismatch" error) an explicit `loop_scope` narrower than a fixture requires.

**Sync fixtures do not run inside any loop.** They are called directly (`run_until_complete` is not involved) and `asyncio.get_running_loop()` raises inside them. Whether `asyncio.get_event_loop()` in a sync fixture returns *the test's* loop depends on ordering: the function-scope loop is created lazily, either by the first async fixture resolved or (if there is none) only *after all fixtures* when the test coroutine is about to run. In the experiment, a sync fixture listed before any async fixture saw a stale (sometimes already-closed) loop from a previous test. The safe way for a sync fixture to hand an object to an async test is to hand a plain object (client, factory, callable) and let the test do the awaiting; if a sync fixture needs the loop, make it depend on an async fixture.

**Everything runs on the main thread.** Fixtures (sync and async), the test coroutine and teardowns all reported `threading.get_ident() == threading.main_thread().ident`. `-n/--workers` is parsed into `RunConfiguration.worker_count` and never read by the executor. Tests with a *non-function* loop scope are additionally batched and run *concurrently* on the shared loop via `asyncio.gather` (interleaving at `await` points), which matters for anything that holds per-test state such as an open DB transaction.

### (B) `--pytest-compat`

**It is a `sys.modules` injection of a rustest-backed shim, not a real pytest.** With the flag, before any conftest or test module is imported, rustest sets `sys.modules["pytest"] = rustest.compat.pytest` and `sys.modules["pytest_asyncio"] = rustest.compat.pytest_asyncio`, and (from Python, slightly earlier) `sys.modules["_pytest"]` and eight `_pytest.*` submodules to `rustest._pytest_stub`. It does this regardless of whether real pytest is installed, so **real pytest is shadowed** under the flag; without the flag, real pytest (if installed) is what `import pytest` gets and rustest can neither load its fixtures nor see its marks.

**Under the shim, `pytest.*` maps onto rustest primitives 1:1:** `pytest.fixture` calls `rustest.decorators.fixture` (same `__rustest_fixture__` attributes, same discovery path); `pytest.mark.<anything>` is `getattr(rustest.mark, name)`, so `@pytest.mark.django_db(transaction=True)` writes the same `__rustest_marks__` entry as `@rustest.mark.django_db(...)` and is visible to `request.node.get_closest_marker("django_db")`; `pytest.skip`, `pytest.fail`, `pytest.raises`, `pytest.parametrize`, `pytest.approx`, `pytest.xfail`, `pytest.Failed/Skipped/XFailed` are the rustest objects themselves. **A consumer keeping `import pytest` lines will therefore reach rustest-django fixtures and markers, but only when running with `--pytest-compat`.** Any *other* `pytest.<Name>` attribute resolves to a dynamically created, silently non-functional stub class rather than raising.

**There is no `pytest_django` shim or mention anywhere in rustest's code.** `import pytest_django` raises `ModuleNotFoundError` in both modes. The only mentions are in docs: "No pytest-django, pytest-flask, pytest-mock plugins" and a section "9. pytest-django: Not currently supported" recommending hand-written fixtures. `pytest_plugins = [...]` in a conftest is supported, but it is just `importlib.import_module` + extraction of `@fixture`-decorated functions, which is exactly the loading path a rustest-django fixture module needs.

## (A) Code pointers

### Test is async: decided by introspection, not by the mark

- `src/execution.rs:49-57` — `is_async_test()` calls `inspect.iscoroutinefunction` on the test callable.
- `src/execution.rs:1588-1644` — `execute_test_case()` calls the test; at `1606-1610` checks `inspect.iscoroutine(result)`; if so `1615` gets the loop (`get_or_create_test_event_loop`), `1618-1628` reads `timeout` from any `asyncio` mark and wraps in `asyncio.wait_for` (`1631-1636`), then `1638-1641` `loop.run_until_complete(coro)`.
- `src/discovery.rs:1884-1918` — fixtures' `is_async` / `is_async_generator` computed from `__code__.co_flags` (`CO_COROUTINE`, `CO_ASYNC_GENERATOR`) with `inspect` fallback; stored on `Fixture` at `src/model.rs:124-126`.
- `python/rustest/decorators.py:117-135` — `fixture()` sets `__rustest_fixture__`, `__rustest_fixture_scope__`, `__rustest_fixture_autouse__`; nothing async-specific. Valid scopes include `package` (`decorators.py:73-78`).

### `@mark.asyncio` semantics

- `python/rustest/decorators.py:535-633` — `mark.asyncio(func=None, *, loop_scope=None, timeout=None)`. `585-589`: `loop_scope` must be one of `function|class|module|session` (no `package`). `602-608`: `loop_scope`/`timeout` are put in the mark's kwargs *only if given*, so a bare `@mark.asyncio` carries `{}` and leaves detection to Rust. `610-623`: on a class, the mark is re-applied to every coroutine method (the only mark that propagates class to methods).
- `src/execution.rs:1256-1280` — `get_explicit_loop_scope_from_marks()` scans all `asyncio` marks for a `loop_scope` kwarg.
- `src/execution.rs:1453-1488` — `determine_test_loop_scope()`: explicit mark (`1460`) > widest async-fixture scope over test params **plus autouse fixtures** (`1464-1484`) > `max(detected, config.default_test_loop_scope)` (`1487`).
- `src/execution.rs:1286-1327` — `detect_required_loop_scope_from_fixtures()` / `analyze_fixture_scope()`: recursive over fixture dependencies; only `is_async || is_async_generator` fixtures widen the scope (`1316-1320`). Sync fixtures never affect loop choice.
- `src/execution.rs:1356-1416` — `validate_loop_scope_compatibility()`: explicit scope narrower than a required async fixture scope produces the "Loop scope mismatch" failure (`1397-1404`); checked at `1500-1507` for single tests and `841-847` for batches.
- `python/rustest/core.py:33-45,152-153` — `asyncio_default_test_loop_scope` / `asyncio_default_fixture_loop_scope` read from `pyproject.toml [tool.pytest.ini_options]` and passed to Rust (`core.py:173-174`).

### Loop lifecycle

- `src/execution.rs:2166-2196` — `FixtureResolver::get_or_create_event_loop(scope)`: one slot per scope (`2168-2174`); reuse if present and not closed (`2177-2185`); else `asyncio.new_event_loop()` + `asyncio.set_event_loop()` (`2188-2190`). `2204-2207`: the test loop is this for `self.test_loop_scope`. Same logic for batches at `1111-1149`.
- `src/execution.rs:259-263` — `FixtureContext` holds `session/package/module/class_event_loop`; function loop lives on the per-test resolver (`1722`).
- `src/execution.rs:1665-1672` — after each test: `finalize_generators(function_teardowns, test-scope loop)` then `close_event_loop(function_event_loop)`. `401-403`: module loop closed when a new module starts; `283-323`: class/module/package/session loops closed with their scope's teardowns.
- `src/execution.rs:2527-2579` — `close_event_loop()`: `asyncio.all_tasks(loop)` cancelled and awaited via `gather(return_exceptions=True)` (`2539-2566`), `loop.shutdown_asyncgens()` (`2571-2573`), `loop.close()` (`2576`).
- `src/execution.rs:2449-2500` — `finalize_generators()`: async-generator teardown via `anext()` on the provided loop (`2461-2472`), falling back to `asyncio.run()` (a *different, throwaway* loop) only when none is provided (`2473-2477`); teardown errors are printed and swallowed (`2488-2497`).

### Async fixtures and which loop they run on

- `src/execution.rs:1915-1958` — async-generator fixture: call, `effective_scope = max(fixture.scope, self.test_loop_scope)` (`1926`), loop from `get_or_create_event_loop(effective_scope)` (`1927`), `anext()` run with `run_until_complete` (`1930-1937`), generator stored in the teardown list of `fixture.scope` (`1940-1956`).
- `src/execution.rs:1990-2008` — `async def` fixture: same loop selection (`2001-2002`), `run_until_complete` (`2005-2008`).
- `src/execution.rs:2009-2015` — sync fixture: plain `call1`; no loop touched.
- `src/execution.rs:1959-1989` — sync generator fixture: `__next__`; no loop touched.

### Threading and concurrency

- `src/execution.rs:161-169` — safety comment on the resolver thread-local: "Access is single-threaded (Python GIL ensures this)". No `thread::spawn`/`rayon` use in `src/execution.rs`; `worker_count` (`src/model.rs:365`) is only referenced in tests (`src/lib.rs:438-491`, `src/model_tests.rs`).
- `src/execution.rs:60-140` — `partition_tests()`: `can_batch = is_async && loop_scope > Function` (`96`); consecutive such tests with the same scope form an `AsyncBatch`.
- `src/execution.rs:800-1030` — `run_async_batch()`: one shared loop (`835`), per-test resolvers, then `run_coroutines_parallel` (`997`). `python/rustest/async_executor.py:112-146` — `asyncio.gather(*tasks)` under `event_loop.run_until_complete`; `async_executor.py:15-18` documents that stdout/stderr capture may interleave.

### Docs (secondary)

- `docs/async-event-loops.md:62-72` (rules), `155-172` (fixture scope decides loop; autouse included; `pyproject.toml` floor), `174-195` (explicit `loop_scope`), `277-292` (mismatch error).
- `docs/advanced/pytest-compat.md:162-167` — "No event_loop fixture; No pytest_asyncio.fixture; Auto mode not supported". The second bullet is inaccurate: `python/rustest/compat/pytest_asyncio.py:60-99` does provide `pytest_asyncio.fixture` (delegating to the compat `fixture`) and it is injected at `src/discovery.rs:41,47`. The first is accurate: `python/rustest/builtin_fixtures.py` defines no `event_loop` fixture (grep is empty).
- `docs/from-pytest/limitations.md:23` — "pytest-asyncio → Built-in `@mark.asyncio`".

## (B) Code pointers

### Wiring

- `python/rustest/cli.py:146-155` — `--pytest-compat` flag ("Intercepts 'import pytest' so existing pytest tests run without code changes").
- `python/rustest/core.py:133-141` — when set: banner (`48-75`, says "Other plugin APIs are stubbed (non-functional)"), then `install_pytest_stubs()`; `159-175` passes `pytest_compat` to `rust.run`.
- `python/rustest/compat/pytest.py:946-991` — `install_pytest_stubs()`: unless a real `_pytest` package is already imported (`961-963`), sets `sys.modules["_pytest"]`, `_pytest.monkeypatch`, `_pytest.config`, `_pytest.outcomes`, `_pytest.nodes`, `_pytest.mark`, `_pytest.mark.structures`, `_pytest.assertion`, `_pytest.assertion.rewrite`, `_pytest.main` to `rustest._pytest_stub` modules.
- `src/discovery.rs:38-50` — `inject_pytest_compat_shim()`: `sys.modules["pytest"] = rustest.compat.pytest`, `sys.modules["pytest_asyncio"] = rustest.compat.pytest_asyncio`. Called at `351-353`, *before* conftest loading (`374-384`) and test-file import (`396-`). `356-362`: markdown code-block tests are disabled in compat mode.
- `python/rustest/_runtime_config.py:74-83` — `is_pytest_compat_mode()` for fixtures that want to know.

### What `pytest.<x>` resolves to under the shim (`python/rustest/compat/pytest.py`)

- `59-73` — imports `fixture, parametrize, skip_decorator, mark, raises, fail, Failed, Skipped, XFailed, xfail, skip` from `rustest.decorators`.
- `586-642` — `fixture(...)` → `rustest.decorators.fixture` (both call forms). Same attributes, so discovery treats it identically to a native fixture.
- `645-654` — `parametrize`, `raises`, `approx`, `skip` (function), `fail`, `Failed`, `Skipped`, `XFailed`, `xfail` are direct aliases.
- `657-709` — `_PytestMarkCompat`: `__getattr__` → `getattr(rustest.mark, name)` (`674-676`), so `pytest.mark.django_db` *is* `rustest.mark.django_db` → `MarkDecorator` → `__rustest_marks__` (see `marker-introspection.md`). Explicit: `parametrize` (`680-682`), `skip` → `skip_decorator` (`684-690`), `skipif`, `xfail`, `asyncio` → `rustest.mark.*` (`692-705`).
- `712-746` `param`, `748-825` `WarningsChecker`, `827-879` `warns`/`deprecated_call`, `881-944` `importorskip`, `567-584` `hookimpl` (no-op decorator).
- `375-421` — `FixtureRequest` (the same class the Rust engine instantiates for the native `request` fixture, `src/execution.rs:2222-2225`), so `request.node.get_closest_marker` works identically in both spellings.
- `1000-1041` — module-level `__getattr__`: any unknown public name (`pytest.Item`, `pytest.Config`, `pytest.Collector`, `pytest.hookspec`, ...) becomes a cached stub class whose `__init__` accepts anything. Imports of pytest plugin code do not fail; they silently do nothing.
- `_pytest_stub/__init__.py:15-33` — every `_pytest*` stub import emits a `DeprecationWarning`. `_pytest_stub/outcomes.py:34-102` — its `Failed`/`Skipped` are *separate classes* from `rustest.decorators.Failed/Skipped`; `_pytest_stub/config.py:34-89` — `Config.getoption/getini` raise `NotImplementedError`, `addinivalue_line` is a no-op; `_pytest_stub/nodes.py`, `main.py`, `mark/structures.py` are empty type-hint classes.

### Skip detection is by exception text, not class

- `src/execution.rs:655-664` — `is_skip_exception(message)`: matches `"rustest.decorators.Skipped"`, `"pytest.skip.Exception"`, or any traceback line starting with `Skipped:` / ending with `.Skipped`. This is why real pytest's `_pytest.outcomes.Skipped` (and the stub's) are also reported as skips.

### Without the flag, with real pytest installed

- `src/discovery.rs:392-393, 476-495` — text scan for `import pytest` and detection of `@pytest.fixture` objects; prints the "cannot load natively ... Run with --pytest-compat" warning (`479-489`) or the softer "Detected `import pytest`" note (`490-494`).
- `src/execution.rs:1867` — "Unknown fixture" errors get the `--pytest-compat` hint when such fixtures were detected.
- Real `@pytest.mark.x` stores into `pytestmark`, which rustest reads only for `skip` (`src/discovery.rs:2121-2130`), never into `__rustest_marks__`.

### `pytest_plugins` / `rustest_fixtures` are plain module imports

- `src/discovery.rs:568-659` — `load_pytest_plugins_fixtures()`: accepts a string or list (`596-605`), temporarily prepends the conftest dir to `sys.path` (`609-614`), `importlib.import_module` each name (`617-632`, failure is a printed warning), and registers every module attribute that `is_function && is_fixture` (`641-652`). No hooks, no entry points.
- `docs/advanced/pytest-plugins.md:10-27, 39` — documents the same ("NOT a plugin system - just module imports").

### Django mentions (docs only)

- `grep -rn -i django src/ python/` → no matches.
- `docs/advanced/pytest-compat.md:134-136` — "Pytest plugins - rustest does not support pytest plugins (by design). No pytest-django, pytest-flask, pytest-mock plugins"; `:279` checklist "Heavy use of pytest plugins (pytest-django, etc.)" under "Not Compatible".
- `docs/advanced/pytest-plugins.md:29-36` — no pluggy hooks, no `pytest11` entry points, no PyPI plugin packages; `:582-635` — "9. pytest-django ... Migration strategy: Not currently supported", three options, a hand-rolled `django_setup` session fixture example, and the admonition "rustest does not have full Django integration"; `:690` — "pytest-django: Use Django's test runner or pytest".

## Experiment

Scratch venvs on Python 3.12.10 (`uv venv -p 3.12`):

- `.venv`: `uv pip install 'rustest==0.18.0'` — `import pytest` → `ModuleNotFoundError` (no real pytest).
- `.venv-pt`: `uv pip install 'rustest==0.18.0' pytest` — real `pytest 9.1.1`.

### A1: loop and thread identity (`a/test_async_probe.py`)

```python
import asyncio, threading
from rustest import fixture, mark
MAIN = threading.main_thread().ident

def _where(tag):
    try: loop_id = id(asyncio.get_running_loop())
    except RuntimeError: loop_id = None
    try: policy_loop = id(asyncio.get_event_loop_policy().get_event_loop())
    except RuntimeError: policy_loop = None
    print(f"[{tag}] running_loop={loop_id} policy_loop={policy_loop} "
          f"thread={threading.get_ident()} is_main={threading.get_ident()==MAIN}")
    return loop_id, policy_loop, threading.get_ident()

@fixture
def sync_fx(): return _where("sync_fx")
@fixture
async def async_fx(): return _where("async_fx")
@fixture
async def async_gen_fx():
    setup = _where("async_gen_fx setup"); yield setup; _where("async_gen_fx teardown")
@fixture(scope="module")
async def async_mod_fx(): return _where("async_mod_fx (module)")
@fixture(scope="session")
async def async_sess_fx(): return _where("async_sess_fx (session)")

async def test_no_mark_function_scope(sync_fx, async_fx, async_gen_fx):
    me = _where("test_no_mark_function_scope")
    assert me[2] == sync_fx[2] == async_fx[2] == async_gen_fx[2]   # same thread
    assert sync_fx[0] is None                                        # no running loop in sync fixture
    assert async_fx[0] == async_gen_fx[0] == me[0]                   # async fixtures share test loop
    assert sync_fx[1] == me[0]                                       # FAILS (see below)

@mark.asyncio
async def test_marked_function_scope(sync_fx, async_fx):
    me = _where("test_marked_function_scope")
    assert async_fx[0] == me[0]
    assert sync_fx[1] == me[0]                                       # FAILS (see below)

async def test_module_fx_a(async_mod_fx, async_fx):
    me = _where("test_module_fx_a"); assert async_mod_fx[0] == me[0] == async_fx[0]
async def test_module_fx_b(async_mod_fx):
    me = _where("test_module_fx_b"); assert async_mod_fx[0] == me[0]
async def test_session_fx(async_sess_fx, async_mod_fx):
    me = _where("test_session_fx"); assert async_sess_fx[0] == me[0]

@mark.asyncio(loop_scope="function")
async def test_explicit_mismatch(async_sess_fx): _where("test_explicit_mismatch")

@mark.asyncio(loop_scope="module")
async def test_explicit_module_1(): _where("test_explicit_module_1")
@mark.asyncio(loop_scope="module")
async def test_explicit_module_2(): _where("test_explicit_module_2")

@fixture
def sync_fx_loop():
    loop = asyncio.get_event_loop()
    print(f"[sync_fx_loop] get_event_loop()={id(loop)} closed={loop.is_closed()}"); return loop
async def test_sync_fixture_sees_loop(sync_fx_loop):
    assert sync_fx_loop is asyncio.get_running_loop()                # FAILS (see below)

def test_sync_test_after(sync_fx): _where("test_sync_test_after (sync test)")
```

`.venv/bin/python -m rustest --no-capture a/test_async_probe.py` → `6 passed, 4 failed`. Output (progress bars removed; loop ids are `id()` values from one run; thread id was `8713766912`, `is_main=True` on every line):

```
[sync_fx]                    running_loop=None        policy_loop=4319033728
[async_fx]                   running_loop=4312024608  policy_loop=4312024608
[async_gen_fx setup]         running_loop=4312024608  policy_loop=4312024608
[test_no_mark_function_scope] running_loop=4312024608 policy_loop=4312024608
[async_gen_fx teardown]      running_loop=4312024608  policy_loop=4312024608
[sync_fx]                    running_loop=None        policy_loop=4312024608   <- previous test's (closed) loop
[async_fx]                   running_loop=4306931104  policy_loop=4306931104   <- new function loop
[test_marked_function_scope] running_loop=4306931104  policy_loop=4306931104
[async_mod_fx (module)]      running_loop=4319033872
[async_fx]                   running_loop=4319033872                           <- function fixture ran on MODULE loop
[test_module_fx_a]           running_loop=4319033872
[test_module_fx_b]           running_loop=4319033872                           <- same module loop reused
[async_sess_fx (session)]    running_loop=4318876048
[test_session_fx]            running_loop=4318876048
  module loop 4319033872 session loop 4318876048 same? False
[test_explicit_module_1]     running_loop=4319033872  policy_loop=4318876048   <- module loop; policy still points at session loop
[test_explicit_module_2]     running_loop=4319033872
[sync_fx_loop] get_event_loop()=4318876048 closed=False                        <- sync fixture got the SESSION loop
[test_sync_fixture_sees_loop] running=4310152976 same_as_sync_fixture=False    <- test got a fresh FUNCTION loop
[sync_fx]                    running_loop=None        policy_loop=4310152976
[test_sync_test_after]       running_loop=None        policy_loop=4310152976
```

Failures: `test_no_mark_function_scope` and `test_marked_function_scope` failed only on `sync_fx[1] == me[0]` (the sync fixture, resolved *before* the async fixture, saw the previous loop); `test_sync_fixture_sees_loop` failed as shown; `test_explicit_mismatch` failed with the engine's "Loop scope mismatch: Test 'test_explicit_mismatch' uses @mark.asyncio(loop_scope="function") but depends on session-scoped async fixture(s): 'async_sess_fx'" message (`src/execution.rs:1397-1404`), the test body never ran.

### A2: ordering decides what a sync fixture sees (`a2/test_order.py`)

```python
@fixture
async def async_first(): return asyncio.get_running_loop()
@fixture
def sync_after_async(async_first): return asyncio.get_event_loop_policy().get_event_loop()
@fixture
def sync_alone(): return asyncio.get_event_loop_policy().get_event_loop()

async def test_sync_dep_on_async(sync_after_async, async_first):
    assert sync_after_async is asyncio.get_running_loop()            # passes
async def test_sync_alone_only(sync_alone):
    assert sync_alone is not asyncio.get_running_loop()              # passes (documents the gotcha)
async def test_param_order_async_then_sync(async_first, sync_alone):
    assert sync_alone is asyncio.get_running_loop()                  # passes
```

`.venv/bin/python -m rustest --no-capture --color never a2/test_order.py` → `3 passed`:

```
[sync_after_async] policy loop=4327346960 == async_first loop? True
[sync_alone] policy loop=4327346960 closed=True          <- stale loop from previous test
[test_sync_alone_only] running=4314811952 sync saw same? False
[sync_alone] policy loop=4324815504 closed=False         <- async_first already created it
[test_param_order_async_then_sync] running=4324815504 sync saw same? True
```

### B: `import pytest` spelling in four configurations (`b/`)

`b/conftest.py` stands in for a rustest-django fixture module (native `rustest.fixture` only):

```python
from rustest import fixture
@fixture
def django_db_probe(request):
    m = request.node.get_closest_marker("django_db")
    print(f"[django_db_probe] nodeid={request.node.nodeid} marker={m!r}")
    return m
```

`b/test_pytest_spelling.py` keeps `import pytest` and uses `@pytest.fixture`, `@pytest.mark.django_db(transaction=True)` with `django_db_probe`, `pytest.raises`, `pytest.fail`, `pytest.skip`, `@pytest.mark.asyncio`; `b/test_marker_only.py` uses only `@pytest.mark.django_db(transaction=True)` + `django_db_probe` and asserts the probe is not `None`.

| run | command | result |
|---|---|---|
| B1 | `.venv/bin/python -m rustest --no-capture b` | `ModuleNotFoundError: No module named 'pytest'` at collection; rustest prints "Note: Detected `import pytest` ... Consider running with --pytest-compat". |
| B2 | `.venv/bin/python -m rustest --no-capture --pytest-compat b` | `5 passed, 1 skipped`. `pytest` is `<module 'rustest.compat.pytest'>`, `pytest.__version__ == "rustest-compat"`, `'_pytest' in sys.modules == True`, `pytest.fixture.__module__ == "rustest.compat.pytest"`, `type(pytest.mark)` is `_PytestMarkCompat`. Probe printed `marker=Mark(name='django_db', args=(), kwargs={'transaction': True})`; the test function has `__rustest_marks__=[{'name': 'django_db', ...}]` and `pytestmark=None`. `pytest.fail` raised `rustest.decorators.Failed`. |
| B3 | `.venv-pt/bin/python -m rustest --no-capture b` (real pytest 9.1.1, no flag) | `3 passed, 2 failed, 1 skipped`. `pytest` is the real `pytest/__init__.py`, `pytest.fixture.__module__ == "_pytest.fixtures"`, `type(pytest.mark)` is `_pytest.mark.structures.MarkGenerator`. Warning "Found @pytest.fixture definitions that rustest cannot load natively: b/test_pytest_spelling.py: pt_fixture". `test_marker_via_pytest_spelling` failed with "Unknown fixture 'pt_fixture' ... Hint: ... Run with --pytest-compat". `test_pytest_fail` failed because real `Failed` derives from `BaseException`. `pytest.skip` was still reported as skipped (string match, `src/execution.rs:656-664`). `@pytest.mark.asyncio` test passed (mark irrelevant). |
| B3b | `.venv-pt/bin/python -m rustest --no-capture --color never b/test_marker_only.py` | `1 failed`: probe printed `marker=None`; function has `__rustest_marks__=None pytestmark=[Mark(name='django_db', args=(), kwargs={'transaction': True})]`. Real pytest marks are invisible to rustest fixtures. |
| B4 | `.venv-pt/bin/python -m rustest --no-capture --pytest-compat b` (real pytest installed, with flag) | Identical to B2: `5 passed, 1 skipped`; `pytest` resolves to `rustest/compat/pytest.py` inside `.venv-pt`, real pytest never imported. |
| B2b | `.venv/bin/python -m rustest --no-capture --color never --pytest-compat b/test_marker_only.py` | `1 passed`, probe sees `Mark(name='django_db', args=(), kwargs={'transaction': True})`. |

### C: skip detection (`c/test_skiptest.py`)

```python
import unittest, rustest
def test_unittest_skiptest(): raise unittest.SkipTest("django-style skip")
def test_rustest_skip(): rustest.skip("rustest-style skip")
```

`.venv/bin/python -m rustest --color never c/test_skiptest.py` → `1 failed, 1 skipped`. `test_unittest_skiptest` is listed under FAILURES with `unittest.case.SkipTest: django-style skip`; `test_rustest_skip` is the skip.

## Consequences for the port

1. **Async support is feasible with native primitives, no plugin needed.** `async_client` / `async_rf` can be plain *sync* fixtures returning `AsyncClient()` / `AsyncRequestFactory()` objects (as pytest-django does); the test awaits them on its own loop. Do not call `asyncio.get_event_loop()` from a sync fixture expecting the test's loop: it is created after the fixtures unless an async fixture precedes it (A1/A2). If rustest-django ever needs the test loop inside a fixture, make that fixture `async def` (it will then run on the test's loop, `src/execution.rs:2001-2002`).
2. **Loop per test is the default and is torn down hard.** With no async fixtures each async test gets a fresh loop that is closed after its function-scoped teardowns (`1665-1672`, `2527-2579`), including `shutdown_asyncgens` and cancellation of leftover tasks. That is friendlier than pytest-asyncio's default for Django, whose `AsyncClient`/`sync_to_async` machinery assumes nothing outlives the loop.
3. **Everything is on the main thread, so `sync_to_async(thread_sensitive=True)` and `database_sync_to_async` behave as they do under `python -m pytest` with pytest-asyncio's default loop policy:** the test coroutine runs on the main thread via `run_until_complete`, and asgiref will dispatch thread-sensitive sync calls to its single-thread executor (a different thread from the fixture code). Consequence for `db`/`transactional_db` in async tests: the connection opened by the sync fixture (main thread) and the one used by ORM calls inside `sync_to_async` (executor thread) are different Django connections, which is pytest-django's documented limitation too. This paragraph's asgiref behaviour is from asgiref, not verified against rustest sources here; what *is* verified is that rustest adds no threads of its own.
4. **Batching changes isolation for wider loop scopes.** Any async test whose loop scope is `class`/`module`/`session` (explicitly, via a wider-scoped async fixture, or via the `pyproject.toml` floor) is run *concurrently* with its neighbours on one loop (`src/execution.rs:96`, `async_executor.py:137-146`). A per-test DB transaction wrapper (`db` fixture) would interleave with other tests' transactions at `await` points. rustest-django should either keep all its fixtures sync (so loop scope stays `function`), or document that `transactional_db`-style fixtures are unsafe together with wider loop scopes.
5. **API/marker spelling: ship native `rustest` spellings; `import pytest` works only under `--pytest-compat`.** `@pytest.mark.django_db(...)`, `@pytest.fixture`, `pytest.skip/fail/raises` all become the identical rustest objects under the shim (`compat/pytest.py:586-709`), so rustest-django's `get_closest_marker("django_db")` sees them (B2/B4). Without the flag they either fail at import (no pytest installed, B1) or silently miss: real pytest marks land in `pytestmark` and are invisible (B3b), and real `@pytest.fixture` objects are not loadable (B3). Document: "either `from rustest import fixture, mark` or run with `--pytest-compat`".
6. **Do not `import pytest` inside rustest-django itself.** The module is loaded through `pytest_plugins`/`rustest_fixtures` (`src/discovery.rs:568-659`) or a conftest; if it imported `pytest` it would only work under the shim (or worse, pick up real pytest). Use `rustest.fixture`, `rustest.mark`, `rustest.skip`, `rustest.fail`, and `rustest.FixtureRequest` for annotations (`python/rustest/__init__.py:21,32-42`). To detect compat mode at runtime use `rustest._runtime_config.is_pytest_compat_mode()` (`_runtime_config.py:74-83`).
7. **No `pytest_django` shim exists, and `pytest.<anything>` never fails.** Under the shim `import pytest_django` still raises `ModuleNotFoundError`, and unknown `pytest.X` names become inert stub classes (`compat/pytest.py:1000-1041`). If rustest-django wants to be a drop-in for consumers' `pytest_plugins = ["pytest_django"]` lines it must be importable under its own name (`rustest_django`) and the docs must tell consumers to change that line; there is nothing to hook.
8. **Skip is detected by exception text.** Raising `rustest.Skipped`/`rustest.skip()` is the supported way (`execution.rs:656-664`). Django's `unittest.SkipTest` (raised by `skipIfDBFeature`, `skipUnlessDBFeature`, and pytest-django's `_skip_if_no_django`-style helpers when ported literally) is reported as a **failure**, not a skip (experiment C). rustest-django must raise `rustest.skip()` / `rustest.Skipped` itself and, where it wraps Django helpers, translate `SkipTest` into it.
9. **Docs vs code.** `docs/advanced/pytest-compat.md:164` says "No pytest_asyncio.fixture", but `rustest.compat.pytest_asyncio.fixture` exists and is injected; treat the shim as the source of truth. The `--pytest-compat` warning text at `src/discovery.rs:487` ("may not support ... async fixtures") is likewise stale: async fixtures are native and the compat `fixture` is the native one.
