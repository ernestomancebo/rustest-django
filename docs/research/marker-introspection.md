# Research: can a rustest fixture read markers and their kwargs?

Resolves [#2](https://github.com/ernestomancebo/rustest-django/issues/2). Part of #1.

Sources: rustest repo `apex-engineers-inc/rustest` at commit `757e0ee27ae55058fa9b84ad57a9dfaa38ac8a93` (version `0.18.0` in `pyproject.toml`), and the `rustest==0.18.0` wheel from PyPI (same version, used for the experiment). File:line pointers below refer to that commit.

## Verdict

**Yes, for function-level marks.** At fixture execution time, `request.node.get_closest_marker("django_db")` returns an object whose `.args` (tuple) and `.kwargs` (dict) carry exactly what was written in `@mark.django_db(transaction=True, databases=[...])`. Presence is also visible as `"django_db" in request.node.keywords`.

**No, via `request.function`.** It is hard-coded to `None`, as are `request.cls` and `request.module`. There is nothing on the request object to walk back to the function.

**No, for class-level marks.** `@mark.django_db(...)` on a test class is stored on the class object only. rustest does not merge class marks into the methods' mark list, so a fixture sees no `django_db` marker on `TestFoo::test_bar`, and `-m django_db` does not select such methods either. The only mark that propagates class-to-methods is `@mark.asyncio`, which does so by special-casing in the decorator itself.

**`-m django_db` filter:** matches on mark *name only*. Kwargs are irrelevant to the filter, so `@mark.django_db` and `@mark.django_db(transaction=True)` are both selected by `-m django_db`.

## How marks are represented

### Python side: `__rustest_marks__` list of dicts

`@mark.<name>` and `@mark.<name>(*args, **kwargs)` both resolve to a `MarkDecorator(name, args, kwargs)`. Its `__call__` appends a plain dict `{"name", "args", "kwargs"}` to a list stored on the decorated object under the attribute `__rustest_marks__`, then returns the object unchanged.

- `python/rustest/decorators.py:483-517` — `MarkDecorator`; `__call__` at 493-507 does `getattr(func, "__rustest_marks__", [])` → append → `setattr`.
- `python/rustest/decorators.py:717-740` — `_MarkDecoratorFactory`: a bare `@mark.x` (single callable positional arg, no kwargs) becomes `MarkDecorator(x, (), {})`; anything else returns a `MarkDecorator(x, args, kwargs)` to be applied later. Note the ambiguity: `@mark.x(some_callable)` with a single callable positional argument is treated as the bare form.
- `python/rustest/decorators.py:610-628` — only `mark.asyncio` iterates a decorated class's coroutine methods and re-applies the mark to each; generic marks have no such step.
- The `kwargs` dict is stored by reference (no copy) at `decorators.py:498-502`, so the fixture later sees the very dict object the test author wrote; mutating it in a fixture would leak across the mark's lifetime.

`pytestmark` (pytest's storage attribute) is only consulted to detect `@pytest.mark.skip` (`src/discovery.rs:2121-2130`, in `check_for_pytest_skip_mark`); it is *not* fed into the general mark list.

### Rust side: `Mark { name, args: PyList, kwargs: PyDict }`

- `src/model.rs:75-115` — `Mark` struct with `is_named()` and `get_kwarg(py, key)`. rustest's own asyncio support reads `loop_scope`/`timeout` kwargs this way (`src/execution.rs:1261-1263`), so kwargs are preserved end-to-end by design.
- `src/discovery.rs:2332-2369` — `collect_marks(value)`: reads `value.__rustest_marks__`, converts each dict into a `Mark` (args tuple → list; kwargs dict kept as-is).
- `src/discovery.rs:1198` — called on each module-level test function.
- `src/discovery.rs:1650` — called on each test *method* (`collect_marks(&method)`), with `method` coming from `inspect.getmembers(cls)` (`discovery.rs:1572`). Nothing in `1555-1680` reads the class's own `__rustest_marks__`; only class-level *parametrization* and *indirect params* are merged (`1567-1568`, `1654-1664`).

### Delivery to the fixture: `FixtureRequest(node_markers=...)`

- `src/execution.rs:1732-1733` — `FixtureResolver` carries `test_marks: Vec<Mark>` for the current test.
- `src/execution.rs:2222-2242` — `create_request_fixture()` instantiates `rustest.compat.pytest.FixtureRequest` with `param`, `node_name`, `nodeid`, and `node_markers=self.build_marker_list()`.
- `src/execution.rs:2244-2254` — `build_marker_list()` emits one dict per mark: `name` (str), `args` (converted back to a tuple, 2256-2262), `kwargs` (the same `PyDict` via `clone_ref`).
- `python/rustest/compat/pytest.py:375-421` — `FixtureRequest.__init__` builds `self.node = Node(name, nodeid, markers=node_markers, config)`; at 416-418 sets `self.function = None`, `self.cls = None`, `self.module = None`. Docstring at 378-380: "Not implemented: function, cls, module, fixturename".
- `python/rustest/compat/pytest.py:128-133` — `MarkerDict` TypedDict `{name: str, args: tuple, kwargs: dict}`.
- `python/rustest/compat/pytest.py:136-170` — `Node`: stores `_markers`, populates `keywords[name] = True` per mark.
- `python/rustest/compat/pytest.py:172-182` — `Node.get_closest_marker(name)`: scans `_markers` in reverse, returns `_MarkerInfo(name, args, kwargs)` or `None`.
- `python/rustest/compat/pytest.py:245-255` — `_MarkerInfo` has attributes `name`, `args`, `kwargs` (same shape as pytest's `Mark`).
- `python/rustest/compat/pytest.py:184-243` — `Node.add_marker(...)` exists too (accepts str, `MarkDecorator`-decorated objects, objects with `.name/.args/.kwargs`, or dicts). There is no `iter_markers()`.

The `request` fixture is the *only* way a fixture gets this; `builtin_fixtures.py:320-352` documents that the Rust engine creates the `FixtureRequest` and the Python-side stub is a fallback.

### `-m` filter semantics

- `src/mark_expr.rs:43-50` — `MarkExpr::matches` for `Name(n)` is `marks.iter().any(|m| m.name == n)`. Name-only; args/kwargs never inspected. Supports `and` / `or` / `not` / parentheses.
- `src/discovery.rs:907-911` — filter applied at collection with `tests.retain(|case| mark_expr.matches(&case.marks))`, using the per-test `marks` produced by `collect_marks`. Therefore class-level marks (not in `case.marks`) also do not affect `-m` selection.

### Docs (secondary)

- `docs/advanced/pytest-compat.md:77-90, 119, 149-151` and `docs/from-pytest/limitations.md:212-215` state `request.node.get_closest_marker(name)` is supported and `request.function`/`cls`/`module` are always `None`.
- `docs/guide/test-classes.md:155-176` shows `@mark.integration` on a class with the comment "Has both @mark.integration and @mark.slow" on a method. Against the code and the experiment below this is inaccurate for non-`asyncio` marks: the method does not carry the class mark.

## Experiment

`rustest==0.18.0` installed with `uv pip install rustest` into a scratch venv (Python 3.12), file `test_marks.py`:

```python
from rustest import fixture, mark

@fixture
def probe(request):
    m = request.node.get_closest_marker("django_db")
    print(f"\n[probe] nodeid={request.node.nodeid} request.function={request.function!r}")
    print(f"[probe] marker={m!r} keywords={request.node.keywords}")
    print(f"[probe] raw node._markers={request.node._markers}")
    return m

@mark.django_db(transaction=True, databases=["default", "other"])
def test_kwargs(probe):
    assert probe.kwargs["transaction"] is True
    assert probe.kwargs["databases"] == ["default", "other"]
    print("[test] test_kwargs.__rustest_marks__ =", test_kwargs.__rustest_marks__)

@mark.django_db
def test_bare(probe):
    assert probe.kwargs == {} and probe.args == ()

def test_unmarked(probe):
    assert probe is None

@mark.django_db(transaction=True)
class TestClassLevel:
    def test_inherits(self, probe):
        print("[test] class-level mark seen by method as:", probe)
        assert probe is not None and probe.kwargs == {"transaction": True}
```

`python -m rustest --no-capture test_marks.py` → `3 passed, 1 failed` (the class-level case fails). Captured output, paths trimmed:

```
[probe] nodeid=.../test_marks.py::test_kwargs request.function=None
[probe] marker=Mark(name='django_db', args=(), kwargs={'transaction': True, 'databases': ['default', 'other']}) keywords={'django_db': True}
[probe] raw node._markers=[{'name': 'django_db', 'args': (), 'kwargs': {'transaction': True, 'databases': ['default', 'other']}}]
[test] test_kwargs.__rustest_marks__ = [{'name': 'django_db', 'args': (), 'kwargs': {'transaction': True, 'databases': ['default', 'other']}}]

[probe] nodeid=.../test_marks.py::test_bare request.function=None
[probe] marker=Mark(name='django_db', args=(), kwargs={}) keywords={'django_db': True}

[probe] nodeid=.../test_marks.py::test_unmarked request.function=None
[probe] marker=None keywords={}

[probe] nodeid=.../test_marks.py::TestClassLevel::test_inherits request.function=None
[probe] marker=None keywords={}
[probe] raw node._markers=[]
[test] class-level mark seen by method as: None
```

`python -m rustest -m django_db test_marks.py` → `Collected 2 tests`, both pass: `test_kwargs` and `test_bare`. `test_unmarked` and `TestClassLevel::test_inherits` are excluded.

`python -m rustest -m "not django_db" test_marks.py` → `Collected 2 tests`: `test_unmarked` and `TestClassLevel::test_inherits`. Confirms the class-marked method is treated as *unmarked* by the filter.

## Minimal working snippet for rustest-django

```python
from rustest import fixture

@fixture
def _django_db_marker(request):
    m = request.node.get_closest_marker("django_db")
    if m is None:
        return None
    # pytest-django defaults; args are positional (transaction, reset_sequences, ...)
    return {
        "transaction": m.kwargs.get("transaction", m.args[0] if m.args else False),
        "reset_sequences": m.kwargs.get("reset_sequences", False),
        "databases": m.kwargs.get("databases", None),
        "serialized_rollback": m.kwargs.get("serialized_rollback", False),
        "available_apps": m.kwargs.get("available_apps", None),
    }
```

## Consequences for the port

1. The `django_db` marker can be spelled `@mark.django_db(...)` with rustest's own `mark` and read from the `db`/`transactional_db`/DB-blocker autouse fixture via `request.node.get_closest_marker("django_db")`. No function-object access is needed.
2. Class-level `@mark.django_db` on a `TestCase`-style class does **not** work in rustest 0.18.0. pytest-django users rely on this (pytest merges class and module marks into each item's `iter_markers()`). Options: document as an unsupported feature (fail loudly per CONTEXT.md), ship a rustest-django class decorator that re-applies the mark to each `test*` method (the same trick `mark.asyncio` uses at `decorators.py:610-623`), or upstream a fix to `src/discovery.rs:1650` to prepend the class's `__rustest_marks__`. Module-level `pytestmark = [...]` is likewise not read.
3. `get_closest_marker` returns the *last-applied* mark of that name (reverse scan), which matches pytest's "closest" semantics for stacked decorators on one function.
4. `-m django_db` works for selecting DB tests regardless of kwargs, but cannot express `transaction=True` and will miss class-marked tests until item 2 is addressed.
5. rustest exposes no `iter_markers()`; code ported from pytest-django that iterates all `django_db` marks must be rewritten against `request.node._markers` (private) or `get_closest_marker` only.
