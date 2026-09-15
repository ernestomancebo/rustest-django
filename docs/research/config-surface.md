# Research: rustest config surface and pyproject access

Resolves [#3](https://github.com/ernestomancebo/rustest-django/issues/3). Part of #1.

Sources: rustest repo `apex-engineers-inc/rustest` at commit `757e0ee27ae55058fa9b84ad57a9dfaa38ac8a93` (version `0.18.0` in `pyproject.toml:7` and `Cargo.toml:3`), the published docs at <https://apex-engineers-inc.github.io/rustest/> (rendered from the same `docs/` tree; checked `guide/fixtures/`), and the `rustest==0.18.0` wheel from PyPI (used for the experiment, Python 3.12). File:line pointers below refer to that commit.

## Verdict

**`request.config` is an empty shell.** It is a `rustest.compat.pytest.Config` built with no options and no ini values; `getoption(x)` returns the default, `getini(x)` returns `""` (or `[]` for a few list-typed names), `rootpath` is `Path.cwd()`, `inipath` is always `None`. The `rustestconfig` fixture is a second, separate `Config` that carries only rustest's own runtime switches (`verbose`, `capture`, `pytest_compat`, `ascii`, `no_color`, `workers`, `fail_fast`, plus three constants). Neither can carry anything a user typed.

**No `[tool.rustest]` table.** rustest reads exactly three keys from `pyproject.toml`, all under `[tool.pytest.ini_options]`: `pythonpath` (Rust side, for `sys.path`), `asyncio_default_test_loop_scope` and `asyncio_default_fixture_loop_scope` (Python side, from `pyproject.toml` relative to the cwd). Nothing else in the file is parsed, stored, or exposed. A fixture module can read `pyproject.toml` itself with `tomllib`; nothing stops it and nothing helps it.

**Unknown CLI flags are rejected.** The CLI is a plain `argparse` parser using `parse_args`; `--ds=x`, `--reuse-db`, `--create-db`, `--no-migrations`, `--liveserver=...`, `-p`, `-o` all exit 2 with `unrecognized arguments`. There is no `parse_known_args`, no `addoption` hook, no plugin registration. `--` does not help: what follows is treated as a test path and fails with `FileNotFoundError`.

**No rootdir concept.** The only "root" rustest computes is for `sys.path` (`find_project_root` walks up from the first test path to a `pyproject.toml`; `find_basedir` walks up past `__init__.py`), and neither value is exposed to Python. From a fixture, the invocation directory is just `os.getcwd()`; rustest never `chdir`s. `Config.rootpath` is literally `Path.cwd()`, so running `rustest .` from `tests/sub/` gives `rootpath == tests/sub`.

**Environment variables and `pyproject.toml` are the two usable channels.** Environment variables pass through untouched (rustest only adds `RUSTEST_RUNNING=1`). `pyproject.toml` is reachable because the fixture module runs as ordinary Python in the same process and can walk up from the conftest directory or the cwd. There is no third channel: no CLI, no ini, no hooks, no `config.option` population.

**`rustest_fixtures` modules are imported once, in-process, at collection time, before any test file is imported, immediately after the declaring `conftest.py` finishes executing.** Import happens via `importlib.import_module(name)` with the conftest's directory temporarily at `sys.path[0]`. Module-level code can run Django setup at that point. **Import-time exceptions are swallowed** (a one-line `Warning:` on stderr, then collection continues), so the tests later fail with the misleading `Unknown fixture 'db'`.

## Code pointers

### CLI: closed `argparse` surface

- `python/rustest/cli.py:52-167` — `build_parser()`: the complete option set is `paths`, `-k/--pattern`, `-m/--marks`, `-n/--workers`, `--no-capture`, `-v`, `--ascii`, `--color`, `--llm`, `--llm-schema`, `--llm-full`, `--no-codeblocks`, `--lf`, `--ff`, `-x`, `--pytest-compat`.
- `python/rustest/cli.py:170-172` — `main()` calls `parser.parse_args(argv)`; argparse exits 2 on anything else. No `parse_known_args`, no extension point.
- `python/rustest/cli.py:202-218` — `run(...)` receives only those parsed values as keyword arguments; `python/rustest/core.py:78-95` is the full signature, and `src/lib.rs:30-49` the matching `#[pyfunction]` signature. Nothing unparsed survives past `cli.py`.
- `pyproject.toml:27` — console script `rustest = "rustest.__main__:main"`; `python/rustest/__main__.py:7-10` calls the same `main`. `python -m rustest` and `rustest` are the same parser.
- `docs/from-pytest/limitations.md:30-34` and `docs/advanced/pytest-compat.md:143-146` — no hook system: `pytest_configure`, `pytest_addoption` etc. do not exist and conftest hooks are ignored.

### `request.config` and `rustestconfig`

- `python/rustest/compat/pytest.py:258-335` — `Config`. `__init__` (264-287) stores `_options` and `_ini_values` dicts (both default to `{}`), builds `option = _OptionNamespace(_options)`, a `pluginmanager` stub, and sets `self.rootpath = Path.cwd()` (286) and `self.inipath = None` (287).
- `python/rustest/compat/pytest.py:289-302` — `getoption(name, default=None, skip=False)`: strips leading dashes, returns `_options.get(clean_name, default)`; with `skip=True` and a missing key it calls `rustest.decorators.skip`.
- `python/rustest/compat/pytest.py:304-322` — `getini(name)`: returns `_ini_values.get(name)`; when absent returns `[]` for `testpaths`, `python_files`, `python_classes`, `python_functions`, `markers`, `filterwarnings`, and `""` for everything else. There is no ini file reading anywhere behind it (docstring at 305 notwithstanding).
- `python/rustest/compat/pytest.py:325-335` — `addinivalue_line` is a documented no-op.
- `python/rustest/compat/pytest.py:375-421` — `FixtureRequest.__init__`: line 406 does `self.config = Config(options=config_options)`; line 403 hard-codes `self.scope = "function"` (a session-scoped fixture sees `request.scope == "function"`, confirmed in the experiment).
- `src/execution.rs:2222-2243` — `create_request_fixture()` instantiates `FixtureRequest` with `param`, `node_name`, `nodeid`, `node_markers` only. `config_options` is never passed, so every `request.config` is `Config(options=None)`: empty `_options`, empty `_ini_values`.
- `python/rustest/builtin_fixtures.py:1128-1185` — `rustestconfig` (session scope): a new `Config(options=runtime_config.copy(), ini_values={markers: [], python_files: [...], python_classes: ["Test"], python_functions: ["test"]})`. It is not the same object as `request.config` (`c is rustestconfig` is `False` in the experiment).
- `python/rustest/_runtime_config.py:16-48` — the full key set of that runtime dict: `verbose`, `capture`, `pytest_compat`, `ascii`, `no_color`, `workers`, `fail_fast`, and constants `assertmode="rewrite"`, `tb="short"`, `strict=False`. Populated once at `python/rustest/core.py:122-130`.
- `python/rustest/builtin_fixtures.py:1188-1239` — `pytestconfig` is an alias of `rustestconfig` that raises `RuntimeError` unless `--pytest-compat` is on.
- `python/rustest/compat/pytest.py:439` — `request.getfixturevalue(name)` exists (and `addfinalizer` at 423 always raises); not relevant to config but worth knowing it is the only dynamic fixture access.
- `docs/guide/fixtures.md:1587-1605` and `docs/advanced/pytest-compat.md:95-110` show `request.config.getoption("--api-url", default=...)` as if options could be supplied; against the code above, only the default can ever come back.

### `pyproject.toml` reads

- `src/python_support.rs:98-117` — `find_project_root(path)`: walk up from the first test path to the first directory containing `pyproject.toml`. Used only for `sys.path`.
- `src/python_support.rs:119-153` — `read_pythonpath_from_pyproject`: parses the file with the `toml` crate and reads exactly `tool.pytest.ini_options.pythonpath`. `src/python_support.rs:227-287` — `setup_python_path` prepends project root, configured pythonpath entries, `find_basedir` results and any `src/` dir to `sys.path`. Called at `src/discovery.rs:348`, before any conftest is loaded.
- `python/rustest/core.py:19-45` — `_read_asyncio_config()`: opens `Path("pyproject.toml")` **relative to the cwd** (not the project root found by Rust), reads `tool.pytest.ini_options.asyncio_default_test_loop_scope` / `asyncio_default_fixture_loop_scope`, and on Python < 3.11 without `tomli` silently returns defaults (25-32). Result is passed to Rust at `core.py:173-174` and stored at `src/model.rs:317-320`.
- `src/model.rs:302-321` — `RunConfiguration` is the whole Rust-side config; there is no map of arbitrary keys.
- `docs/guide/project-structure.md:19-72, 357` — documents `pythonpath` as the only supported pyproject setting and states `pytest.ini` is not read at all.
- Nothing in `python/`, `src/` or `docs/` mentions a `tool.rustest` table (grep over the tree at this commit is empty; rustest's own `pyproject.toml:51-122` defines `tool.maturin`, `tool.poe.tasks`, `tool.ruff`, `tool.basedpyright`, `tool.uv`, `tool.pytest.ini_options`, `tool.pytest_codeblocks` only).

### Working directory and paths

- `src/python_support.rs:31-46` — `PyPaths::materialise()` canonicalises the CLI paths relative to the process cwd and errors with `Path '...' does not exist` otherwise (this is what `-- --reuse-db` hits).
- `src/model.rs:559-589` — `to_relative_path` uses `std::env::current_dir()` for display only. No `set_current_dir` anywhere in `src/` or `python/rustest/` (grep).
- `src/model.rs:365` — `worker_count` is computed but `grep -i worker src/execution.rs` finds no use: tests run sequentially in the one interpreter that parsed the CLI (experiment: module import pid == test pid with `-n 4`). Anything set in `os.environ` or `django.setup()` state at import time is therefore visible to every test.

### Environment variables

- `python/rustest/core.py:155-180` — the only env var rustest touches: sets `RUSTEST_RUNNING=1` for the duration of `run()` and restores the previous value afterwards. `docs/CHANGELOG.md:199` advertises it "for detecting rustest execution context".
- `src/execution.rs:2130` — `RUSTEST_DEBUG_AUTOUSE` is the only env var read on the Rust side (debug output).
- `python/rustest/cli.py:12-49` — `is_ci_environment()` reads `CI`, `GITHUB_ACTIONS`, etc. purely for the colour default.
- `docs/guide/cli.md:722-735` — "Rustest respects standard Python environment variables": `PYTHONPATH`, `PYTHONDONTWRITEBYTECODE`, `PYTHONDEVMODE`. Nothing is filtered or cleared; `os.environ` inherited from the shell is what fixtures see (experiment below).

### How `rustest_fixtures` is loaded

- `src/discovery.rs:333-420` — `discover_tests` order: `materialise` paths (345) → `setup_python_path` (348) → optional pytest shim (351-353) → `discover_conftest_paths_parallel` (369) → **load every conftest sequentially** (374-384) → find test files (387) → per test file, re-check parent conftests (398-405) then `collect_from_file` (409). Test modules are imported only in that last step, so conftests and their `rustest_fixtures` modules are fully executed before any `test_*.py` runs its module body.
- `src/discovery.rs:185-233` — which conftests: every `conftest.py` under the given directories (skipping excluded dirs) plus every `conftest.py` in the ancestors of each input path up to the filesystem root (214-230). A project-root `conftest.py` is therefore picked up when running `rustest tests/`.
- `src/discovery.rs:711-765` — `load_conftest_fixtures`: (717-718) execute the conftest via `load_python_module` (module name from `infer_module_names`, e.g. `rustest_module_0` when `tests/` has no `__init__.py`, or a dotted package path when it does; `src/discovery.rs:2482-2518`); (736-745) read `rustest_fixtures` from the module dict, falling back to `pytest_plugins`; (749-750) pass `conftest_dir = path.parent()`; (753-762) then collect the conftest's own fixtures.
- `src/discovery.rs:2450-2479` — `load_python_module` uses `importlib.util.spec_from_file_location` + `exec_module` and registers the module in `sys.modules` under the inferred name (2476). The conftest therefore has a real `__file__` and is findable in `sys.modules` by the time its `rustest_fixtures` modules import.
- `src/discovery.rs:588-659` — `load_pytest_plugins_fixtures`: (596-605) value is a `str` or `list[str]`; any other type is silently ignored. (609-614) `sys.path.insert(0, conftest_dir)`; (617-622) `importlib.import_module(module_name)` for each name, so **names are absolute module paths** resolved against `conftest_dir` first and then the normal `sys.path` (which already has the project root and `src/` prepended, and site-packages after). An installed distribution `rustest_django` is importable by that name; a local `tests/fixtures/db.py` is importable as `fixtures.db`. (624-631) import failure → `eprintln!("Warning: Failed to import pytest plugin module ...")` and `continue`; not a collection error. (641-651) only `types.FunctionType` objects that `is_fixture` (i.e. `@rustest.fixture`-decorated) are extracted; anything the module re-exports via `from x import *` also qualifies since it is scanned via `__dict__`. (656) `sys.path.remove(conftest_dir)` afterwards.
- `src/discovery.rs:1981-2020` — `build_fixture_from_value` reads scope, generator/async flags, `autouse`, params, and name from the fixture object, so session-scoped and autouse fixtures declared in the external module behave exactly like ones written in the conftest.
- `src/discovery.rs:770-812` — merge order per test file: built-ins, then conftest fixtures farthest-to-nearest (a `rustest_fixtures` module's fixtures live in the map of the conftest that declared them), then the test module's own; later entries override earlier ones by name. Consumers can override any rustest-django fixture in a nearer conftest or the test file.
- `docs/guide/fixtures.md:495-580` — the user-facing description; 576-580 explicitly: "Rustest does not support ... setuptools entry points (`pytest11`) ... Advanced plugin features (pytest-cov, pytest-django, etc.)". The published page at `apex-engineers-inc.github.io/rustest/guide/fixtures/` carries the same text and no `[tool.rustest]` mention.

### Can the fixture module learn the conftest's directory?

Not via any API. Three facts give it away regardless:

1. During the *first* import of the module, `sys.path[0]` is the directory of the conftest that listed it (`src/discovery.rs:614`). Capture it at module import time.
2. The declaring conftest is already in `sys.modules` with `__file__` set (`src/discovery.rs:2476`, exec finished at 718 before 750 runs). `[m.__file__ for m in sys.modules.values() if getattr(m, "__file__", "").endswith("conftest.py")]` returns it (experiment below).
3. The Python call stack at import time contains no conftest frame (import is driven from Rust after the conftest finished), so `inspect.stack()` is useless for this. Experiment output: only `importlib`, `rustest/core.py`, `rustest/cli.py`, and the console script.

Caveat for (1): if the same module name is listed by several conftests, or a test module imported it earlier, the module body runs only once and `sys.path[0]` reflects the first importer.

## Experiment

`rustest==0.18.0` installed with `uv venv --python 3.12` + `uv pip install rustest==0.18.0` into a scratch venv. Project layout:

```
proj/
  pyproject.toml     # [tool.rustest] and [tool.rustest-django] tables, plus
                     # [tool.pytest.ini_options] DJANGO_SETTINGS_MODULE = "proj.settings_pytest"
  manage.py          # dummy
  tests/
    conftest.py      # prints at import; rustest_fixtures = ["rd_fixtures"]
    rd_fixtures.py   # prints import-time state, reads pyproject with tomllib, defines fixtures
    sub/test_cfg.py  # def test_cfg(probe): assert probe.getoption("ds") is None
```

`rd_fixtures.py` (abridged):

```python
import os, sys, inspect, tomllib
from pathlib import Path
from rustest import fixture

print(f"[rd_fixtures] importing; __name__={__name__} __file__={__file__}")
print(f"[rd_fixtures] cwd={os.getcwd()} sys.argv={sys.argv}")
print(f"[rd_fixtures] sys.path[0]={sys.path[0]}")
print(f"[rd_fixtures] RUSTEST_RUNNING={os.environ.get('RUSTEST_RUNNING')!r} "
      f"DJANGO_SETTINGS_MODULE={os.environ.get('DJANGO_SETTINGS_MODULE')!r}")
conftests = [m.__file__ for m in list(sys.modules.values())
             if getattr(m, "__file__", None) and m.__file__.endswith("conftest.py")]
print(f"[rd_fixtures] conftest modules already in sys.modules={conftests}")
print(f"[rd_fixtures] python frames on stack at import: {[f.filename for f in inspect.stack()[1:]]}")

def _find_pyproject(start: Path):
    for d in [start, *start.parents]:
        if (d / "pyproject.toml").is_file():
            return d / "pyproject.toml"

_pp = _find_pyproject(Path(conftests[0]).parent if conftests else Path.cwd())
_tool = tomllib.loads(_pp.read_text())["tool"] if _pp else {}
print(f"[rd_fixtures] pyproject={_pp} tool.rustest={_tool.get('rustest')} "
      f"tool.rustest-django={_tool.get('rustest-django')}")
os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      _tool.get("rustest", {}).get("django_settings_module", "unset"))

@fixture(scope="session", autouse=True)
def _session_probe(request):
    print(f"[session_probe] scope={request.scope} config._options={request.config._options} "
          f"rootpath={request.config.rootpath}")
    yield

@fixture
def probe(request, rustestconfig):
    c = request.config
    print(f"[probe] type(request.config)={type(c).__module__}.{type(c).__name__}")
    print(f"[probe] request.config._options={c._options} _ini_values={c._ini_values}")
    print(f"[probe] request.config.rootpath={c.rootpath} inipath={c.inipath} cwd={Path.cwd()}")
    print(f"[probe] getoption('ds')={c.getoption('ds')!r} "
          f"getoption('--reuse-db', default='DFLT')={c.getoption('--reuse-db', default='DFLT')!r} "
          f"getini('DJANGO_SETTINGS_MODULE')={c.getini('DJANGO_SETTINGS_MODULE')!r}")
    print(f"[probe] request.config is rustestconfig? {c is rustestconfig}; "
          f"rustestconfig._options={rustestconfig._options}")
    print(f"[probe] rustestconfig._ini_values={rustestconfig._ini_values} rootpath={rustestconfig.rootpath}")
    print(f"[probe] os.environ DJANGO_SETTINGS_MODULE={os.environ.get('DJANGO_SETTINGS_MODULE')!r}")
    return c
```

### Run 1: `rustest tests/ --no-capture` from `proj/` (paths trimmed to `.../proj`)

```
[conftest] importing; __name__=rustest_module_0 __file__=.../proj/tests/conftest.py cwd=.../proj
[conftest] end of module body
[rd_fixtures] importing; __name__=rd_fixtures __file__=.../proj/tests/rd_fixtures.py
[rd_fixtures] cwd=.../proj sys.argv=['../.venv/bin/rustest', 'tests/', '--no-capture']
[rd_fixtures] sys.path[0]=.../proj/tests
[rd_fixtures] RUSTEST_RUNNING='1' DJANGO_SETTINGS_MODULE=None
[rd_fixtures] conftest modules already in sys.modules=['.../proj/tests/conftest.py']
[rd_fixtures] python frames on stack at import: ['<frozen importlib._bootstrap>', ..., '.../importlib/__init__.py', '.../site-packages/rustest/core.py', '.../site-packages/rustest/cli.py', '.../.venv/bin/rustest']
[rd_fixtures] pyproject=.../proj/pyproject.toml tool.rustest={'django_settings_module': 'proj.settings', 'reuse_db': True} tool.rustest-django={'settings': 'proj.settings_alt'}
✓ Collected 1 tests from 1 files (25ms)
[probe] type(request.config)=rustest.compat.pytest.Config
[probe] request.config._options={} _ini_values={}
[probe] request.config.rootpath=.../proj inipath=None cwd=.../proj
[probe] getoption('ds')=None getoption('--reuse-db', default='DFLT')='DFLT' getini('DJANGO_SETTINGS_MODULE')=''
[probe] request.config is rustestconfig? False; rustestconfig._options={'verbose': 0, 'capture': 'no', 'pytest_compat': False, 'ascii': False, 'no_color': False, 'workers': None, 'fail_fast': False, 'assertmode': 'rewrite', 'tb': 'short', 'strict': False}
[probe] rustestconfig._ini_values={'markers': [], 'python_files': ['test_*.py', '*_test.py'], 'python_classes': ['Test'], 'python_functions': ['test']} rootpath=.../proj
[probe] os.environ DJANGO_SETTINGS_MODULE='proj.settings'
[session_probe] scope=function config._options={} rootpath=.../proj
✓ 1 passed in 7ms
```

Observations: conftest body completes before the fixture module imports; the fixture module sees the conftest in `sys.modules` and its dir at `sys.path[0]`; `[tool.pytest.ini_options] DJANGO_SETTINGS_MODULE` is not surfaced by `getini`; the `[tool.rustest]` table is neither read by rustest nor rejected; the value set into `os.environ` at import time is visible inside the fixture.

### Run 2: unknown flags (stdout/stderr suppressed, exit codes recorded)

```
rustest --ds=foo tests/                     -> rustest: error: unrecognized arguments: --ds=foo      exit 2
rustest tests/ --reuse-db                   -> unrecognized arguments: --reuse-db                    exit 2
rustest tests/ --no-migrations              -> exit 2
rustest tests/ --liveserver=localhost:8000  -> exit 2
rustest tests/ -p rustest_django            -> exit 2
rustest tests/ -o DJANGO_SETTINGS_MODULE=x  -> exit 2
python -m rustest tests/ --create-db        -> exit 2
rustest tests/ -- --reuse-db                -> FileNotFoundError: Path '--reuse-db' does not exist   exit 1
```

### Run 3: `rustest . --no-capture` from `proj/tests/sub/`

```
[rd_fixtures] cwd=.../proj/tests/sub sys.argv=['../../../.venv/bin/rustest', '.', '--no-capture', '--color', 'never']
[rd_fixtures] pyproject=.../proj/pyproject.toml tool.rustest={...} tool.rustest-django={...}
[probe] request.config.rootpath=.../proj/tests/sub inipath=None cwd=.../proj/tests/sub
[session_probe] scope=function config._options={} rootpath=.../proj/tests/sub
✓ 1 passed
```

`rootpath` follows the cwd, not the project. The ancestor `tests/conftest.py` was still loaded (via `discover_conftest_paths_parallel` 214-230), and walking up from it found the right `pyproject.toml`. Note `core.py:34` would look for `pyproject.toml` in `tests/sub/` and find nothing, so rustest's own asyncio defaults are silently wrong in this invocation; rustest-django must not copy that cwd-relative approach.

### Run 4: environment passthrough

`DJANGO_SETTINGS_MODULE=env.settings RUSTEST_DJANGO_REUSE_DB=1 rustest tests/ --no-capture`:

```
[rd_fixtures] RUSTEST_RUNNING='1' DJANGO_SETTINGS_MODULE='env.settings'
[probe] os.environ DJANGO_SETTINGS_MODULE='env.settings'
```

### Run 5: `-n 4` and process identity

Added `tests/sub/test_pid.py` printing `os.getpid()` at module import and inside two tests: `rustest tests/ -n 4 --no-capture` printed the same pid (`79561`) for module import and both tests, `3 passed`. One interpreter, no worker processes.

### Run 6: import failure in a `rustest_fixtures` module

`proj2/tests/conftest.py`: `rustest_fixtures = ["broken_fixtures"]`; `broken_fixtures.py` raises `RuntimeError("DJANGO_SETTINGS_MODULE is not set")` at module level after defining nothing; `test_broken.py` requests `db`.

```
Warning: Failed to import pytest plugin module 'broken_fixtures': RuntimeError: DJANGO_SETTINGS_MODULE is not set
✓ Collected 1 tests from 1 files (2ms)
  ✗ tests/test_broken.py
FAILURES
test_uses_db (tests/test_broken.py)
ValueError: Unknown fixture 'db'.
Available fixtures: cache, capfd, caplog, capsys, mocker, monkeypatch, pytestconfig, request, rustestconfig, tmp_path, ...
✗ 1 failed in 1ms
```

The real error is a single stderr line above the progress bar; the failure users read is `Unknown fixture 'db'`.

## Recommended channels for rustest-django

Given the above, only two channels exist and both are fully under rustest-django's control:

1. **`pyproject.toml` `[tool.rustest-django]` table** (project-level defaults, the replacement for `[tool.pytest.ini_options]` keys). Read it in the fixture module with `tomllib` (stdlib on 3.11+; rustest declares `requires-python >= 3.10` at `pyproject.toml:10`, so depend on `tomli; python_version < "3.11"`). Locate the file by walking up from the declaring conftest's directory (captured from `sys.path[0]` at first import, or from the `conftest.py` entries in `sys.modules`), falling back to walking up from `os.getcwd()`. Do **not** use a bare `Path("pyproject.toml")` like `core.py:34`. Use the distribution's own tool name (`rustest-django`), not `[tool.rustest]`, which rustest does not define today and may claim later.
2. **Environment variables** (per-invocation overrides, the replacement for CLI flags): `DJANGO_SETTINGS_MODULE` as-is (it is already the variable pytest-django honours second after `--ds`), plus a `RUSTEST_DJANGO_*` family for the flags with no existing variable: `RUSTEST_DJANGO_REUSE_DB`, `RUSTEST_DJANGO_CREATE_DB`, `RUSTEST_DJANGO_MIGRATIONS` (`0`/`1`), `RUSTEST_DJANGO_LIVESERVER`. Precedence env > pyproject, mirroring pytest-django's CLI > env > ini with the CLI layer removed.

Mapping of the pytest-django surface:

| pytest-django | rustest-django channel |
|---|---|
| `--ds` / `DJANGO_SETTINGS_MODULE` env / ini `DJANGO_SETTINGS_MODULE` | `DJANGO_SETTINGS_MODULE` env, else `[tool.rustest-django] settings` (or `django_settings_module`) |
| `--dc` / `DJANGO_CONFIGURATION` | out of scope (#3) |
| `--reuse-db` / `--create-db` | `RUSTEST_DJANGO_REUSE_DB` / `RUSTEST_DJANGO_CREATE_DB` env, else `reuse_db` key |
| `--no-migrations` / `--migrations` | `RUSTEST_DJANGO_MIGRATIONS=0/1` env, else `migrations` key |
| `--liveserver` | `RUSTEST_DJANGO_LIVESERVER` env, else `liveserver` key (pytest-django itself already reads `DJANGO_LIVE_TEST_SERVER_ADDRESS`) |
| ini `django_find_project` | `find_project` key; the search for `manage.py` must start from the conftest dir / cwd since there is no rootdir |
| ini `django_debug_mode` | `debug_mode` key |
| ini `FAIL_INVALID_TEMPLATE_VARS` | `fail_invalid_template_vars` key |

Keys under `[tool.pytest.ini_options]` (`DJANGO_SETTINGS_MODULE`, `django_find_project`, ...) could be read as a compatibility fallback since the file is being parsed anyway; that is a design decision for the follow-up ticket, not a rustest constraint.

## Consequences for the port

1. There is no runner-option surface to plug into. `request.config.getoption("--reuse-db")` will always return the default, so any pytest-django code path that consults `config.getoption`/`config.getini`/`config.option` must be rewritten to consult rustest-django's own settings object, populated from env + `[tool.rustest-django]`.
2. Django setup can and should happen at import time of the fixture module: it runs after `sys.path` is configured (`discovery.rs:348`) and before any test module imports (`discovery.rs:374-384` vs `396-409`), in the single process that executes the tests. That is the rustest equivalent of pytest-django's `pytest_load_initial_conftests`/`pytest_configure`. Test modules importing models at module level therefore work.
3. Never raise at import time. rustest swallows the exception (`discovery.rs:624-631`) and the user sees `Unknown fixture 'db'`. Catch configuration errors during import, store them, and re-raise them with the original message from the fixtures (`django_db_setup`, `db`, `settings`, ...) so the failure is loud and attributable, per the CONTEXT.md "fail loudly" rule for unsupported features.
4. "rootdir" for `manage.py` discovery (`django_find_project`) and for `pyproject.toml` must be derived by rustest-django: walk up from the declaring conftest's directory (`sys.path[0]` at first import / `sys.modules` scan) and from `os.getcwd()`. `rustestconfig.rootpath` is the cwd and unusable as a project root when users run from a subdirectory.
5. `rustest_fixtures = ["rustest_django"]` (or the distribution's fixture-module path) is imported with plain `importlib.import_module`, so an installed package works with no path tricks; only `@rustest.fixture` functions in the module's `__dict__` are collected, so the module must re-export every fixture it wants visible (star-import from submodules is fine). Fixture `scope`/`autouse` are honoured from that module.
6. `request.scope` is hard-coded to `"function"` (`compat/pytest.py:403`), so pytest-django code that branches on `request.scope` (e.g. `_django_db_helper`) needs a rewrite.
7. Because tests never run in separate processes (`-n` is not wired into execution), a single `os.environ["DJANGO_SETTINGS_MODULE"] = ...` set during fixture-module import is enough; no per-worker re-initialisation is required in 0.18.0. This should be re-verified if upstream ever implements process-based workers.
