# Research: pytest-django port matrix (hook-dependent vs portable code)

Resolves [#7](https://github.com/ernestomancebo/rustest-django/issues/7). Part of #1.

Sources: pytest-django repo `pytest-dev/pytest-django` `main` at commit `67f97981cd444cabbbe4562ff172c466d85b4d1b` (`git describe`: `v4.14.0-1-g67f9798`, i.e. one commit after the 4.14.0 tag, dated 2026-08-10). rustest repo `apex-engineers-inc/rustest` at commit `757e0ee27ae55058fa9b84ad57a9dfaa38ac8a93` (version `0.18.0`), the same commit as `marker-introspection.md`. Django `5.2.6` from PyPI (`django/test/testcases.py`) and CPython 3.11.8 `unittest/case.py` are cited where the behaviour of rustest's unittest runner on Django test classes matters. Unqualified `plugin.py`, `fixtures.py` etc. paths are `pytest_django/<file>` at the pytest-django commit; `pytest.py` means `python/rustest/compat/pytest.py` at the rustest commit.

## Verdict

**87 symbols audited: 46 portable as-is (a), 26 hook/config-dependent and must be redesigned (b), 15 out of scope per the map (c).** Five of those carry a "fog" tier tag (`live_server`, `_live_server_helper`, `LiveServer`, `_django_setup_unittest`, `django_db_reset_sequences`) because the map has not decided them.

The (a) column is bigger than it looks in the plugin: every user-visible fixture body (`client`, `rf`, `admin_*`, `settings`, `mailoutbox`, `django_capture_on_commit_callbacks`, the whole of `asserts.py`, `DjangoDbBlocker`, `Settings`, `_disable_migrations`, the `PytestDjangoTestCase` construction) is plain Django code with no pytest dependency beyond `pytest.skip`.

The (b) column clusters into **five redesign seams**, not 26 separate problems:

1. **Runner options.** `pytest_addoption` + every `config.getoption`/`getvalue`/`getini` read (`django_db_use_migrations`, `django_db_keepdb`, `django_db_createdb`, `django_test_environment`, `_initialize_django`, `live_server`, `_assert_num_queries`). rustest's `request.config` is an empty stub: `create_request_fixture` passes no `config_options` (`src/execution.rs:2222-2242`), so `getini` returns `""` and `getoption` returns the default (`pytest.py:289-323`). Only the `rustestconfig` fixture carries real values, and only rustest's own seven keys (`python/rustest/_runtime_config.py:15-45`).
2. **Startup hooks.** `pytest_load_initial_conftests` / `_initialize_django` / `pytest_configure` / `_setup_django` / `pytest_unconfigure` (settings discovery, `django.setup()`, initial `block()`, final `restore()`). Must become import-time code in the fixture module plus a session-scoped autouse fixture.
3. **`config.stash` singletons.** `blocking_manager_key`, `django_db_blocker`, `report_header_key`. Trivial: module-level instance.
4. **`request.fixturenames`.** Absent in rustest 0.18 (no occurrence anywhere under `python/rustest` or `src`). pytest-django uses it to decide *transactional vs not*, *reset_sequences*, *serialized_rollback*, and *live_server* in `_django_db_helper` (`fixtures.py:236-244`), in `_live_server_helper` (`fixtures.py:656`), and in `_get_databases_for_test` (`fixtures.py:123,133-134`). This is the one seam where the redesign changes fixture *topology*, not just where a value comes from.
5. **Collection-time knowledge.** `django_db_setup` reads `request.session.items` to precompute which DB aliases to create and which to serialize (`fixtures.py:183`, `146-159`). rustest exposes no collected-item list to fixtures (`Node.session = None`, `pytest.py:164`; `FixtureRequest` has no `session` attribute, `pytest.py:383-421`). `is_django_unittest` (`request.cls`) is in the same bucket: `request.cls` is hard-coded `None` (`pytest.py:417`).

Everything in (c) is either a collection hook (`pytest_collectstart`, `pytest_itemcollected`, `pytest_collection_modifyitems`), a marker the map excluded (`urls`, `django_isolate_apps`, `ignore_template_errors`), the template-vars feature, xdist, django-configurations, `runner.py`, or the standalone `django_db_serialized_rollback` fixture.

## The matrix

Kind abbreviations: `fx(scope[,auto])` fixture; `hook`; `cls`; `fn` helper; `const`. Tier tags in Notes: T1/T2/T3 from the map, "fog" = undecided, "none" = not named by the map.

| File | Symbol (lines) | Kind | Class | pytest APIs used | Notes |
|---|---|---|---|---|---|
| `__init__.py` | `__version__` (1-5) | const | a | — | Ship own `_version`. |
| `__init__.py` | re-exports `DjangoAssertNumQueries`, `DjangoCaptureOnCommitCallbacks`, `Settings`, `DjangoDbBlocker` (8-18) | API | a | — | Names must survive the name swap. `Settings` exported since 4.13.0 (`docs/changelog.rst:39`), `DjangoDbBlocker` since 4.7.0 (`changelog.rst:189`). |
| `plugin.py` | `SETTINGS_MODULE_ENV`, `CONFIGURATION_ENV`, `INVALID_TEMPLATE_VARS_ENV` (62-64) | const | a | — | Only the first is in scope; the other two belong to (c) features. |
| `plugin.py` | `pytest_addoption` (70-157) | hook | b | `pytest.hookimpl`, `pytest.Parser`, `parser.getgroup`, `group.addoption`, `parser.addini` | Registers `--reuse-db`, `--create-db`, `--ds`, `--dc`, `--nomigrations`/`--no-migrations`, `--migrations`, `--liveserver`, `--fail-on-template-vars`; ini `DJANGO_CONFIGURATION`, `DJANGO_SETTINGS_MODULE`, `django_find_project` (bool, default True), `django_debug_mode` (default `"False"`), `FAIL_INVALID_TEMPLATE_VARS`. Becomes the runner-option schema (§4). `--dc`, `--fail-on-template-vars` are (c). `--liveserver` fog. |
| `plugin.py` | `PROJECT_FOUND`, `PROJECT_NOT_FOUND`, `PROJECT_SCAN_DISABLED` (160-178) | const | a | — | Message text mentions `pytest.ini`; reword. |
| `plugin.py` | `_handle_import_error` (181-193) | fn | a | — | Wraps `ImportError`/`ImproperlyConfigured` (Django ≥ 6.2 change noted at 183-185). |
| `plugin.py` | `_add_django_project_to_path` (196-230) | fn | a | — (input is pytest's CLI `args`) | Pure, but rustest hands a fixture module no argv. Calling it with `[]` scans cwd only (212-216). T1 settings discovery. |
| `plugin.py` | `_setup_django` (233-249) | fn | b | `config.stash[blocking_manager_key]` | `django.setup()` if `apps.ready` is False (245-246), then `block()` **unconditionally** (248-249). Called twice in a normal run (397, 411) so two `block()` frames are pushed; that is why `pytest_unconfigure` loops (524-527). |
| `plugin.py` | `_get_boolean_value` (252-268) | fn | a | — | Note it raises on `""` (263-268); rustest's stub `getini` returns `""` for unknown keys (`pytest.py:304-323`), so a naive port of `django_test_environment` would crash. |
| `plugin.py` | `report_header_key` (271) | const | c | `pytest.StashKey` | Report-header cosmetics; rustest has no header hook. |
| `plugin.py` | `pytest_load_initial_conftests` (274-330) | hook | b | `pytest.hookimpl`, `early_config.addinivalue_line("markers", …)` ×4, `parser.parse_known_args`, `early_config.stash` ×2, `options.version`, `options.help` | Marker registration is unnecessary: rustest has no `--strict-markers` and compat `Config.addinivalue_line` is a no-op (`pytest.py:325-336`). Creates the `DjangoDbBlocker` (322) and calls `_initialize_django` (325). Tolerates failure only for `--help`/`--version` (326-330). |
| `plugin.py` | `_initialize_django` (333-397) | hook body | b | `early_config.getini` ×3 (`django_find_project`, `FAIL_INVALID_TEMPLATE_VARS`, `DJANGO_SETTINGS_MODULE`/`DJANGO_CONFIGURATION`), `options.itv/ds/dc` | Precedence option > env > ini (360-371). Sets `os.environ["DJANGO_SETTINGS_MODULE"]` (378), force-loads `dj_settings.DATABASES` inside `_handle_import_error` (391-394), then `_setup_django` (397). django-configurations branch (380-387) is (c). T1 core. |
| `plugin.py` | `pytest_configure` (400-411) | hook | b | `pytest.hookimpl(trylast=True)`, `config.getoption("version")`, `config.getoption("help")` | Second-chance `_setup_django` for users who call `settings.configure()` in their own `pytest_configure` (405-410). rustest has no such user hook; the equivalent is "consumer configures settings in `conftest.py` before rustest-django's session fixture runs". |
| `plugin.py` | `pytest_report_header` (414-425) | hook | c | `config.stash` | Cosmetic. |
| `plugin.py` | `pytest_collectstart` (431-448) | hook | c | `pytest.Collector`, `pytest.Class`, `collector.obj`, `collector.add_marker` | Django `tags` on `SimpleTestCase` classes → marks. Needs a collection hook; tier none. |
| `plugin.py` | `pytest_itemcollected` (452-469) | hook | c | `pytest.Item`, `pytest.Function`, `item.obj`, `item.cls`, `item.add_marker` | Same for method-level `tags`. |
| `plugin.py` | `pytest_collection_modifyitems` (472-517) | hook | c | `pytest.hookimpl(tryfirst=True)`, `pytest.Item`, `item.cls`, `item.get_closest_marker`, `item.fixturenames`, `items.sort` | Reordering, explicitly out of scope. Detail in §6. |
| `plugin.py` | `pytest_unconfigure` (520-527) | hook | b | `config.stash` | `while blocker.is_active: restore()`. Becomes teardown of the session autouse fixture. |
| `plugin.py` | `django_test_environment` (530-555) | fx(session, auto) | b | `request.config.getini("django_debug_mode")` | Body (`setup_test_environment(debug=…)` / `teardown_test_environment()`) is portable. `"keep"` → `debug=None` (545-546). T1. |
| `plugin.py` | `django_db_blocker` (558-585) | fx(session) | b | `request.config.stash[blocking_manager_key]` | Returns `None` when Django is not configured (581-582). T1; return the module singleton. |
| `plugin.py` | `_django_db_marker` (588-593) | fx(function, auto) | a | `request.node.get_closest_marker("django_db")`, `request.getfixturevalue("_django_db_helper")` | Both exist in rustest 0.18 (`pytest.py:172-182`, `439-476`; Rust bridge `src/execution.rs:210-230`). Class-level marks are invisible (see `marker-introspection.md`). |
| `plugin.py` | `_django_setup_unittest` (596-633) | fx(class, auto) | b | `request.cls` (via `is_django_unittest`), `from _pytest.unittest import TestCaseFunction`, monkeypatch of `TestCaseFunction.runtest` (611-620, 633), `request.cls.databases`, `request.getfixturevalue("django_db_setup")` | `request.cls` is always `None` in rustest (`pytest.py:417`) so the guard (602) can never pass; `_pytest.unittest` is not in rustest's `_pytest` stub (`python/rustest/_pytest_stub/__init__.py:21,35`). §2. Tier fog: the map never names Django `TestCase` classes. |
| `plugin.py` | `_dj_autoclear_mailbox` (636-644) | fx(function, auto) | a | — | `mail.outbox.clear()` if present. T1 (part of `mailoutbox`). |
| `plugin.py` | `mailoutbox` (647-659) | fx(function) | a | `pytest.skip` (via `skip_if_no_django`) | Depends on `django_mail_patch_dns` and `_dj_autoclear_mailbox`. T1. |
| `plugin.py` | `django_mail_patch_dns` (662-670) | fx(function) | a | `monkeypatch` fixture (`MonkeyPatch.setattr`) | rustest ships `monkeypatch` (`python/rustest/builtin_fixtures.py:311-317`) with `setattr` (`79-114`). T1. |
| `plugin.py` | `django_mail_dnsname` (673-676) | fx(function) | a | — | Returns `"fake-tests.example.com"`. T1. |
| `plugin.py` | `_django_set_urlconf` (679-701) | fx(function, auto) | c | `request.node.get_closest_marker("urls")`, `pytest.Mark` | `urls` marker out of scope. |
| `plugin.py` | `_django_isolate_apps` (704-721) | fx(function, auto) | c | `request.node.get_closest_marker("django_isolate_apps")` | Out of scope. |
| `plugin.py` | `django_isolated_apps` (724-734) | fx(function) | c | `pytest.UsageError` | Out of scope. |
| `plugin.py` | `_fail_for_invalid_template_variable` (737-819) | fx(session, auto) | c | `pytest.fail` (798), `pytest.MonkeyPatch.context()` (802), `mp.setitem` | `--fail-on-template-vars` out of scope. |
| `plugin.py` | `_template_string_if_invalid_marker` (822-839) | fx(function, auto) | c | `request.keywords.get("ignore_template_errors")`, `monkeypatch.setattr` | Out of scope. |
| `plugin.py` | `_django_clear_site_cache` (842-854) | fx(function, auto) | a | — | `Site.objects.clear_cache()` when `django.contrib.sites` installed. Tier none; trivially kept for parity. |
| `plugin.py` | `_DatabaseBlockerContextManager` (860-873) | cls | a | — | `__exit__` → `restore()`. |
| `plugin.py` | `DjangoDbBlocker` (876-937) | cls | a | — (`_ispytest` constructor guard, 882-887) | §3. The ticket's `_DatabaseBlocker` is this class's older name. |
| `plugin.py` | `blocking_manager_key` (941) | const | b | `pytest.StashKey[DjangoDbBlocker]` | The ticket's `_blocking_manager`. Replace with a module-level instance. |
| `plugin.py` | `validate_urls` (944-954) | fn | c | `pytest.Mark` | Out of scope. |
| `plugin.py` | `validate_django_isolate_apps` (957-965) | fn | c | `pytest.Mark` | Out of scope. |
| `fixtures.py` | `_DjangoDbDatabases`, `_DjangoDbAvailableApps`, `_DjangoDb` (27-30) | types | a | — | `TYPE_CHECKING` only. |
| `fixtures.py` | `django_db_modify_db_settings_tox_suffix` (56-63) | fx(session) | a | `pytest.skip` | Reads `TOX_PARALLEL_ENV`. T1 (`django_db_modify_db_settings*`). |
| `fixtures.py` | `django_db_modify_db_settings_xdist_suffix` (66-73) | fx(session) | c | `request.config.workerinput` (xdist) | xdist out of scope. Keep the *name* as a no-op so the override chain (76-89) still resolves. |
| `fixtures.py` | `django_db_modify_db_settings_parallel_suffix` (76-81) | fx(session) | a | `pytest.skip` | Aggregator. T1. |
| `fixtures.py` | `django_db_modify_db_settings` (84-89) | fx(session) | a | `pytest.skip` | The documented user override point. T1. |
| `fixtures.py` | `django_db_use_migrations` (92-95) | fx(session) | b | `request.config.getvalue("nomigrations")` | `not nomigrations`. T1; §4. |
| `fixtures.py` | `django_db_keepdb` (98-102) | fx(session) | b | `request.config.getvalue("reuse_db")` | T1/T3; §4. |
| `fixtures.py` | `django_db_createdb` (105-109) | fx(session) | b | `request.config.getvalue("create_db")` | §4. |
| `fixtures.py` | `_get_databases_for_test` (112-143) | fn | b | `pytest.Item`, `item.cls`, `item.fixturenames`, `item.get_closest_marker` | Per-item: `TransactionTestCase` subclasses use `cls.databases`/`cls.serialized_rollback` (118-121); else marker (124-132); else fixture names (133-135); `None` → `(DEFAULT_DB_ALIAS,)`, `"__all__"` → `connections` (138-143). |
| `fixtures.py` | `_get_databases_for_setup` (146-159) | fn | b | `Sequence[pytest.Item]` | Union over all items; derived from `DiscoverRunner.get_databases()` (151). |
| `fixtures.py` | `django_db_setup` (162-203) | fx(session) | b | `request.session.items` (183), `request.config.option.verbose` (187, 199), `request.node.warn(pytest.PytestWarning(...))` (201-203) | The `setup_databases`/`teardown_databases` calls are portable. The alias precomputation is the collection-time dependency (§6). T1. |
| `fixtures.py` | `_django_db_helper` (206-309) | fx(function) | b | `request.cls` (via `is_django_unittest`, 212), `request.node.get_closest_marker` (218), `request.fixturenames` ×4 (239, 241, 243) | Lines 246-309 (`PytestDjangoTestCase`) are pure. §1. T1. |
| `fixtures.py` | `_django_db_signature` (312-320) | fn | a | — | The marker's defaults. §1. |
| `fixtures.py` | `validate_django_db` (323-334) | fn | a | `pytest.Mark` (`.args`, `.kwargs`) | rustest's `_MarkerInfo` has the same two attributes (`pytest.py:245-255`). |
| `fixtures.py` | `_disable_migrations` (337-355) | fn | a | — | §4. |
| `fixtures.py` | `_set_suffix_to_test_databases` (358-373) | fn | a | — | Skips sqlite without explicit `TEST.NAME` and `:memory:` (364-370). |
| `fixtures.py` | `db` (379-393) | fx(function) | a | — | Body is a docstring; requests `_django_db_helper`. Its *meaning* is fixed by the helper, see next rows. T1. |
| `fixtures.py` | `transactional_db` (396-409) | fx(function) | b | — | Body is a docstring; the helper detects it only via `"transactional_db" in request.fixturenames` (239). Needs a new signalling mechanism. T1. |
| `fixtures.py` | `django_db_reset_sequences` (412-425) | fx(function) | b | — | Same mechanism (241). Not named by the map: fog. |
| `fixtures.py` | `django_db_serialized_rollback` (428-446) | fx(function) | c | — | Standalone fixture out of scope; the marker kwarg stays in scope. |
| `fixtures.py` | `client` (449-456) | fx(function) | a | `pytest.skip` | `Client()`. T1. |
| `fixtures.py` | `async_client` (459-466) | fx(function) | a | `pytest.skip` | `AsyncClient()`. T2. |
| `fixtures.py` | `django_user_model` (469-474) | fx(function) | a | — | `get_user_model()`; depends on `db`. T1. |
| `fixtures.py` | `django_username_field` (477-481) | fx(function) | a | — | `USERNAME_FIELD`. T1. |
| `fixtures.py` | `admin_user` (484-512) | fx(function) | a | — | `get_by_natural_key` then `create_superuser` (499-511). T1. |
| `fixtures.py` | `admin_client` (515-525) | fx(function) | a | — | `force_login`. T1. |
| `fixtures.py` | `rf` (528-535) | fx(function) | a | `pytest.skip` | T1. |
| `fixtures.py` | `async_rf` (538-545) | fx(function) | a | `pytest.skip` | T2. |
| `fixtures.py` | `Settings` (548-592) | cls | a | — (`_is_pytest_django` constructor guard, 554-561) | §5. The ticket's `SettingsWrapper` is this class's older name. |
| `fixtures.py` | `settings` (595-602) | fx(function) | a | `pytest.skip` | Yields `Settings`, then `_finalize()`. T1. |
| `fixtures.py` | `live_server` (605-637) | fx(session) | b | `request.config.getvalue("liveserver")` | Precedence option > `DJANGO_LIVE_TEST_SERVER_ADDRESS` > `"localhost"` (629-633). Fog. |
| `fixtures.py` | `_live_server_helper` (640-665) | fx(function, auto) | b | `request.fixturenames` (656), `request.getfixturevalue("transactional_db")` (660), `request.getfixturevalue("live_server")` (662) | Enables/disables `modify_settings(ALLOWED_HOSTS)` per test (663-665). Fog. |
| `fixtures.py` | `DjangoAssertNumQueries` (668-680) | Protocol | a | — | T2. |
| `fixtures.py` | `_assert_num_queries` (683-727) | fn | b | `config.getoption("verbose")` (706), `pytest.fail` (727) | `rustestconfig.getoption("verbose")` supplies verbosity (`builtin_fixtures.py:1128-1186`); `rustest.fail` (`decorators.py:951`). T2. |
| `fixtures.py` | `django_assert_num_queries` (730-733) | fx(function) | b | `pytestconfig` fixture | Swap to `rustestconfig`. T2. |
| `fixtures.py` | `django_assert_max_num_queries` (736-739) | fx(function) | b | `pytestconfig` fixture | Same. T2. |
| `fixtures.py` | `DjangoCaptureOnCommitCallbacks` (742-751) | Protocol | a | — | T1. |
| `fixtures.py` | `django_capture_on_commit_callbacks` (754-759) | fx(function) | a | — | Returns `TestCase.captureOnCommitCallbacks` (Django 5.2.6 `testcases.py:1499`). T1. |
| `asserts.py` | `MessagesTestCase` (15-16) | cls | a | — | `MessagesTestMixin + TestCase`. T1. |
| `asserts.py` | `test_case` (19) | const | a | — | One instance, `MessagesTestCase("run")`. |
| `asserts.py` | `_wrapper` (22-29) | fn | a | — | `functools.wraps` around the bound method. |
| `asserts.py` | `assertions_names` + export loop (32-44) | module code | a | — | Collects `assert*` from `TestCase`, `SimpleTestCase`, `LiveServerTestCase`, `TransactionTestCase`, `MessagesTestMixin`. Imports Django at module import (11-12). Ship `asserts.pyi` too. T1. |
| `live_server_helper.py` | `LiveServer` (6-91) | cls | a | — | Pure Django: `LiveServerThread` (45), daemon thread (53), in-memory sqlite `connections_override` (20-27), `modify_settings(ALLOWED_HOSTS)` (47-49) toggled by `_live_server_helper`. Tier fog. |
| `lazy_django.py` | `skip_if_no_django` (14-17) | fn | a | `pytest.skip` | → `rustest.skip` (`decorators.py:993`). |
| `lazy_django.py` | `django_settings_is_configured` (20-33) | fn | a | — | Env var or `django.conf.settings.configured`. |
| `lazy_django.py` | `get_django_version` (36-40) | fn | a | — | |
| `django_compat.py` | `_User`, `_UserModel` (10-19) | types | a | — | |
| `django_compat.py` | `is_django_unittest` (22-30) | fn | b | `request.cls` / `item.cls` | Always `False` under rustest (`pytest.py:417`). |
| `runner.py` | `TestRunner` (6-52) | cls | c | `pytest.main` | `manage.py test` bridge, maps `--keepdb` → `--reuse-db` (48-49). Not in the ticket's file list; tier none. |
| `pyproject.toml` | `[project.entry-points.pytest11] django = "pytest_django.plugin"` (91-92) | packaging | b | pluggy entry point | Replaced by `rustest_fixtures = ["rustest_django"]` in the consumer's `conftest.py`. |

## §1 The `django_db` marker: kwargs, defaults, and TestCase construction

Signature and defaults, `fixtures.py:312-320`:

```python
def _django_db_signature(
    transaction: bool = False,
    reset_sequences: bool = False,
    databases: _DjangoDbDatabases = None,      # Literal["__all__"] | Iterable[str] | None
    serialized_rollback: bool = False,
    available_apps: _DjangoDbAvailableApps = None,  # list[str] | None
) -> _DjangoDb: ...
```

`validate_django_db` calls it as `_django_db_signature(*marker.args, **marker.kwargs)` (`fixtures.py:334`), so positional use in that order is accepted, and unknown kwargs raise `TypeError` from Python itself. The registered marker help text (`plugin.py:283-293`) lists only the first four; `available_apps` is undocumented there but accepted (`docs/changelog.rst:212-213`). The docstring at `fixtures.py:331-332` claims `reset_sequences`, `serialized_rollback`, `available_apps` are "only allowed when combined with transaction", but the code enforces nothing: it *forces* transactional when `reset_sequences` is set and leaves the other two alone.

Resolution in `_django_db_helper` (`fixtures.py:218-244`): marker values, or all-defaults if no marker (228-234); then

- `transactional = transaction or reset_sequences or ("transactional_db" in fixturenames or "live_server" in fixturenames)` (236-240)
- `reset_sequences |= "django_db_reset_sequences" in fixturenames` (241)
- `serialized_rollback |= "django_db_serialized_rollback" in fixturenames` (242-244)

Class construction (`fixtures.py:246-309`), inside `django_db_blocker.unblock()`:

1. Base is `TransactionTestCase` if transactional else `TestCase` (250-253).
2. `class PytestDjangoTestCase(base)` sets class attrs `reset_sequences`, `serialized_rollback`; sets `databases` and `available_apps` only when not `None` so Django's class defaults apply otherwise (260-266). Django defaults: `TransactionTestCase.databases = {DEFAULT_DB_ALIAS}`, `reset_sequences = False`, `available_apps = None`, `serialized_rollback = False` (Django 5.2.6 `testcases.py:1097-1117`).
3. For the non-transactional case it overrides `setUpClass`/`tearDownClass` to call `super(django.test.TestCase, cls)` (281-289), i.e. it *skips* `TestCase.setUpClass` (`_enter_atomics`, `setUpTestData`; Django `testcases.py:1407-1416`) and `TestCase.tearDownClass` (`_rollback_atomics` and connection close; `1439-1445`). The comment at 268-280 explains why: `TestCase.tearDownClass` closes all connections, which defeats higher-scoped transactions.
4. `PytestDjangoTestCase.setUpClass()` (291); instantiate with `methodName="__init__"` (293); call `_pre_setup()` unless `_pre_setup_ran_eagerly` (294-301, the flag `TransactionTestCase.setUpClass` sets for non-`TestCase` subclasses, Django `testcases.py:1120-1124`); `yield`; `_post_teardown()` (305); `tearDownClass()` (307); `doClassCleanups()` (309).

So a per-test "TestCase instance" is built; the only pytest dependencies are the three inputs (marker, `fixturenames`, `is_django_unittest`).

## §2 Django `unittest.TestCase` classes

pytest-django does not run Django test classes itself; pytest's unittest integration does. pytest-django adds three things:

1. `_django_setup_unittest` (`plugin.py:596-633`), a class-scoped autouse fixture. When `request.cls` is a `SimpleTestCase` subclass (602, via `django_compat.py:22-30`) it replaces `_pytest.unittest.TestCaseFunction.runtest` with `self._testcase(result=self)` (611-620), i.e. it routes through Django's `SimpleTestCase.__call__` → `_setup_and_call` (Django `testcases.py:315-321`, `345-372`) rather than pytest's default `debug()` path; the comment at 606-608 cites pytest#5991 and pytest-django#824. If `request.cls.databases` is truthy it requests `django_db_setup` and holds `django_db_blocker.unblock()` for the class (622-631); otherwise `nullcontext()`.
2. `_django_db_helper` yields immediately for unittest items (`fixtures.py:212-214`): no `PytestDjangoTestCase`, Django's own `setUpClass`/`_pre_setup` do the work.
3. Collection-time: `pytest_collection_modifyitems` classifies `TransactionTestCase` subclasses as DB tests, transactional unless also a `TestCase` (`plugin.py:484-488`); `_get_databases_for_test` reads `cls.databases`/`cls.serialized_rollback` (`fixtures.py:118-121`); `pytest_collectstart`/`pytest_itemcollected` turn Django `tags` into marks (431-469).

Under rustest 0.18 none of this can attach: `request.cls` is `None` (`pytest.py:417`) and `_pytest.unittest` is not stubbed. rustest does discover `unittest.TestCase` subclasses (`src/discovery.rs:1236-1241`, `1417-1429`) and runs each method through generated code `test_instance = test_class(name); test_instance()` (`src/discovery.rs:1721-1745`). Consequences for Django classes:

- `test_instance()` is `TestCase.__call__` → `run(result=None)` (CPython `unittest/case.py:677-678`, `589-600`), which for Django is `SimpleTestCase.__call__` → `_setup_and_call(result)` (Django `testcases.py:315-321`). So `_pre_setup`/`_post_teardown` run per test, but **`setUpClass`/`tearDownClass` are never called** (they belong to `TestSuite`, not `run()`), so `TestCase._enter_atomics`/`setUpTestData` never run and `TransactionTestCase._pre_setup_ran_eagerly` is never set.
- With `result=None`, stdlib `run()` creates a `defaultTestResult()` and Django's `_setup_and_call` reports errors via `result.addError` (`testcases.py:366-372`). Nothing in `src/execution.rs` reads a `TestResult` (grep for `TestResult`/`wasSuccessful` only hits rustest's own `PyTestResult`). Whether an assertion failure inside a Django `TestCase` method is surfaced at all under rustest is therefore **unknown** and must be checked by experiment before deciding this tier.
- unittest items are discovered with `marks: Vec::new()` (`src/discovery.rs:1458-1470`), so `@mark.django_db` on them is invisible either way.

## §3 The DB blocker

`DjangoDbBlocker` (`plugin.py:876-937`) monkeypatches one attribute: `django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection`, at the *class* level (893-901), so every connection alias is affected at once.

- `_dj_db_wrapper` property lazily saves the real `ensure_connection` on first access (896-899).
- `block()` pushes the current method onto `_history` and installs `_blocking_wrapper` (920-924); `unblock()` pushes and installs the saved real method (914-918); both return `_DatabaseBlockerContextManager` whose `__exit__` calls `restore()` (860-873), which pops `_history` (926-932). `is_active` is `bool(_history)` (934-937).
- `_blocking_wrapper` raises `RuntimeError("Database access not allowed, use the \"django_db\" mark, or the \"db\" or \"transactional_db\" fixtures to enable it.")` with `__tracebackhide__` (906-912).
- Lifecycle: created in `pytest_load_initial_conftests` (322), first `block()` in `_setup_django` (248-249) from both `pytest_load_initial_conftests` (397) and `pytest_configure` (411); unblocked in `django_db_setup` around `setup_databases`/`teardown_databases` (185, 197), in `_django_db_helper` around the whole test (246), and in `_django_setup_unittest` for a DB-using class (626); drained in `pytest_unconfigure` (524-527). Exposed to users through the `django_db_blocker` fixture (558-585).

The class is (a). Only its storage (`config.stash`) and its start/end hooks are (b). Ticket names `_DatabaseBlocker`/`_blocking_manager` are the pre-4.7 names.

## §4 `--reuse-db`, `--create-db`, `--no-migrations`

| Flag / ini | Registered | Read by | Effect |
|---|---|---|---|
| `--reuse-db` → `reuse_db` | `plugin.py:73-80` | `django_db_keepdb`, `fixtures.py:98-102` | `django_db_setup`: `keepdb=True` passed to `setup_databases` when `keepdb and not createdb` (180-181); `teardown_databases` skipped entirely when keepdb (196-203). |
| `--create-db` → `create_db` | `plugin.py:81-88` | `django_db_createdb`, `fixtures.py:105-109` | Only cancels `keepdb` (180). Alone it is a no-op. |
| `--nomigrations` / `--no-migrations` → `nomigrations` (store_true), `--migrations` (store_false) | `plugin.py:105-119` | `django_db_use_migrations` = `not nomigrations`, `fixtures.py:92-95` | `_disable_migrations()` (`fixtures.py:337-355`): `settings.MIGRATION_MODULES = DisableMigrations()` (every app "has" module `None`, so Django treats all apps as unmigrated and syncs tables from models) and `migrate.Command` swapped for a `verbosity=0` subclass. |
| `--ds` → `ds` | `plugin.py:89-96` | `_initialize_django`, `plugin.py:373-378` | Sets `os.environ["DJANGO_SETTINGS_MODULE"]`; precedence option > env > ini. |
| `--liveserver` | `plugin.py:124-128` | `live_server`, `fixtures.py:629-633` | Address; fallback env `DJANGO_LIVE_TEST_SERVER_ADDRESS`, then `localhost`. |
| ini `django_find_project` (bool, True) | `plugin.py:134-139` | `_initialize_django`, `plugin.py:344-351` | Whether to scan for `manage.py` and `sys.path.insert(0, …)` (`196-230`). |
| ini `django_debug_mode` (`"False"`) | `plugin.py:140-144` | `django_test_environment`, `plugin.py:544-548` | `setup_test_environment(debug=…)`; `"keep"` → `None`. |

Each of `django_db_use_migrations`, `django_db_keepdb`, `django_db_createdb` is a *public, overridable* session fixture (documented as the override mechanism), so the port keeps the three fixture names and only changes where the default value comes from. Django's own `manage.py test --keepdb` maps to `--reuse-db` in `runner.py:48-49`.

## §5 The `settings` fixture

`Settings` (`fixtures.py:548-592`; `SettingsWrapper` in older releases, exported as `pytest_django.Settings` since 4.13.0):

- `__init__` requires `_is_pytest_django=True` and stores `_to_restore: list[override_settings]` through `object.__setattr__` to dodge its own `__setattr__` (554-563).
- `__setattr__(attr, value)` → `override_settings(**{attr: value})`, `.enable()`, push (576-581).
- `__delattr__(attr)` → an *empty* `override_settings()`, `.enable()`, then `delattr(django.conf.settings, attr)`, push (565-574). The empty override snapshots the wrapped settings so `.disable()` restores the deleted key.
- `__getattr__` → `getattr(django.conf.settings, attr)` (583-586).
- `_finalize()` disables in reverse order and clears the list (588-592).

The `settings` fixture (595-602) is `skip_if_no_django(); wrapper = Settings(_is_pytest_django=True); yield wrapper; wrapper._finalize()`. Pure Django; (a). Note it does not depend on `django_test_environment`, and each `override_settings.enable()` fires Django's `setting_changed` signal, which is what resets caches, templates, etc.

## §6 Test ordering and other collection-hook reliance

`pytest_collection_modifyitems` (`plugin.py:472-517`, `tryfirst=True`) sorts items with a stable sort by `get_order_number` (483-515):

- `TransactionTestCase` subclass → `uses_db=True`, `transactional = not issubclass(cls, TestCase)` (484-488).
- Otherwise the `django_db` marker via `validate_django_db`: `transactional = transaction or reset_sequences` (490-500); then `transactional |= "transactional_db" or "live_server" in fixturenames`, `uses_db |= "db" in fixturenames` (504-508).
- Key: transactional → 1, non-transactional DB → 0, no DB → 2 (510-515). Order is therefore *non-transactional DB tests, then transactional, then no-DB*, mirroring Django's runner (comment 480-481).

Other places that need the collection to be complete or hook into it:

- `django_db_setup` → `_get_databases_for_setup(request.session.items)` (`fixtures.py:183`, `146-159`, `112-143`): the set of aliases to create and the subset to serialize is computed from every collected item's class attrs, marker, and fixture names *before* the first DB test runs. Without collection access the port must either set up all `settings.DATABASES` aliases (Django's `DiscoverRunner` default when `databases` is unrestricted), read the alias list from a runner option, or set databases up lazily on first demand per alias. `serialized_aliases` matters only for `serialized_rollback`, which is marker-kwarg-only in v1.
- `pytest_collectstart` / `pytest_itemcollected` (`plugin.py:431-469`): Django `tags` → pytest marks. (c).
- `_get_databases_for_test` also uses `item.fixturenames` and `item.cls` (`fixtures.py:118-135`).

## rustest equivalents needed

### Known to exist in rustest 0.18 (verified at commit `757e0ee`)

- `@fixture(scope=…, autouse=…)` with scopes `function`, `class`, `module`, `package`, `session` (`python/rustest/decorators.py:17`, `38-125`); generator fixtures with teardown (`src/execution.rs:238` onward, `TeardownCollector`). Autouse fixtures are resolved after the test's explicit arguments, widest scope first (`src/execution.rs:887-921`, `2108-2148`).
- `request.node.get_closest_marker(name)` → object with `.name/.args/.kwargs` (`pytest.py:172-182`, `245-255`); `request.node.keywords` (`pytest.py:166-170`). Function-level marks only (see `marker-introspection.md`).
- `request.getfixturevalue(name)` backed by the Rust resolver (`pytest.py:439-476`, `src/execution.rs:162-230`, `src/lib.rs:80-96`).
- `monkeypatch` fixture with `setattr`/`delattr`/`setitem`/`delitem`/`setenv`/`context()`/`undo()` (`python/rustest/builtin_fixtures.py:59-225`, `311-317`); `rustest.MonkeyPatch` exported (`python/rustest/__init__.py:61`).
- `rustest.skip(reason)`, `rustest.fail(reason)`, `Skipped`, `Failed`, `xfail` (`decorators.py:945-1040`; exports `__init__.py:44-82`).
- `rustestconfig` session fixture with `getoption("verbose")` etc. from `_runtime_config` (`builtin_fixtures.py:1128-1186`; keys `verbose`, `capture`, `pytest_compat`, `ascii`, `no_color`, `workers`, `fail_fast`, `assertmode`, `tb`, `strict` at `_runtime_config.py:37-48`). `pytestconfig` exists but is documented as compat-mode only (`builtin_fixtures.py:1189-1215`).
- `mark.usefixtures(...)` (`decorators.py:697-708`, applied at `src/execution.rs:930`); arbitrary `@mark.<name>(**kwargs)`.
- `unittest.TestCase` discovery and per-method runner (`src/discovery.rs:1236-1241`, `1417-1470`, `1721-1745`), with the caveats in §2.
- A `pyproject.toml` reader precedent using `tomllib` (`python/rustest/core.py:18-44`), currently reading only `[tool.pytest.ini_options]` asyncio keys.
- Fixture-module loading via `rustest_fixtures` in `conftest.py` (map, hard constraint; `conftest.py` discovery at `src/discovery.rs:181-232`).

### Must be provided by rustest-django itself

- **Runner-option reader**: env var > `[tool.rustest-django]` > default, for `reuse_db`, `create_db`, `nomigrations`, `DJANGO_SETTINGS_MODULE` (`--ds`), `django_find_project`, `django_debug_mode`, and (if `live_server` lands) `liveserver`. Replaces `pytest_addoption` and every `getoption`/`getvalue`/`getini`. Keep `django_db_use_migrations`/`django_db_keepdb`/`django_db_createdb` as overridable session fixtures that read it.
- **Startup**: settings discovery (`_add_django_project_to_path` with `[]`, `_initialize_django`'s precedence chain minus `--dc`), `django.setup()`, first `block()`, at fixture-module import or in a session-scoped autouse fixture; teardown drains the blocker (replaces `pytest_load_initial_conftests`, `pytest_configure`, `pytest_unconfigure`).
- **Module-level `DjangoDbBlocker` instance** replacing `config.stash[blocking_manager_key]`; `django_db_blocker` returns it.
- **A `request.fixturenames` replacement** for `_django_db_helper`: how `transactional_db` (and `django_db_reset_sequences`, `live_server` if kept) tell the helper which mode to build. Candidates: distinct internal helpers per mode requested via `getfixturevalue`, a module-level per-test flag set by `transactional_db` before it requests the helper, or one parametrised helper. This is a design decision for the spec, not a lookup.
- **A `request.session.items` replacement** in `django_db_setup` for the alias set (see §6).
- **`is_django_unittest` replacement**, or an explicit v1 decision that Django `TestCase` classes are unsupported (fail loudly per the map).
- `request.node.warn(PytestWarning)` → `warnings.warn`; `pytest.UsageError` → own exception type; `pytest.skip`/`pytest.fail` → `rustest.skip`/`rustest.fail` (one-line swaps).
- Class-level `django_db` mark propagation (open item from `marker-introspection.md`).
- No marker registration is needed (rustest has no strict-markers check).

### Unknown, needs checking

- Whether a failing Django `TestCase` method under rustest's unittest runner fails the run at all (§2, second bullet), and whether autouse fixtures from a fixture module run for unittest-discovered items (they have `class_name: Some(...)`, `src/discovery.rs:1466`; fixture-module autouse fixtures have `class_name: None`, so `src/execution.rs:2117-2122` should include them, but this is unverified).
- Whether `getfixturevalue` of a *session*-scoped fixture (`django_db_setup`) from a *function*-scoped fixture caches at session scope and runs its teardown at session end (`resolve_for_request` in `src/execution.rs` not audited).
- Relative teardown order of two session fixtures (DB teardown must run while the blocker is unblocked, before the blocker is drained).
- Whether `pytestconfig` raises outside `--pytest-compat` (docstring says so, `builtin_fixtures.py:1194-1197`; body not audited) — relevant only if the port keeps `pytestconfig` as the name.
- Whether `import pytest` / `pytest.mark.django_db` under `--pytest-compat` reaches a fixture module's `get_closest_marker` (map open question).

## Consequences for the port

1. Port the (a) rows verbatim, swapping `pytest.skip`/`pytest.fail` for `rustest.skip`/`rustest.fail`. That covers every T1/T2 user-visible fixture body plus `asserts.py`, `DjangoDbBlocker`, `Settings`, and the `PytestDjangoTestCase` builder.
2. The spec must decide the five seams in the Verdict, in this order of coupling: runner-option reader → startup/session fixture → blocker singleton → `fixturenames` replacement (changes `db`/`transactional_db` internals) → alias set for `django_db_setup`.
3. `django_db_setup` cannot keep its "compute aliases from collected items" behaviour; pick one of the three alternatives in §6 and record it in the spec, because it changes multi-DB behaviour (T2 pick).
4. Django `TestCase` classes are neither in nor out of the map. Given §2, the cheapest defensible v1 is "unsupported, fail loudly" unless the unittest-runner experiment shows rustest surfaces their failures.
5. Drop the (c) rows but keep two names as no-ops for parity: `django_db_modify_db_settings_xdist_suffix` (override chain) and the marker names `urls`/`django_isolate_apps`/`ignore_template_errors` should raise the unsupported-feature error rather than be silently ignored.
6. `live_server`, `_live_server_helper`, `LiveServer` stay fog; note that `_live_server_helper` depends on the same `fixturenames` seam as `transactional_db`, so resolving seam 4 unblocks it too.
