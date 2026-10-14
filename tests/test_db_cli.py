import textwrap
from pathlib import Path

from _helpers import run_rustest
from rustest import parametrize


def _project(path: Path, tests: str) -> None:
    (path / "settings.py").write_text(
        'SECRET_KEY = "consumer"\n'
        "INSTALLED_APPS = []\n"
        'DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", '
        '"NAME": ":memory:"}}\n'
    )
    (path / "pyproject.toml").write_text(
        '[tool.rustest-django]\nsettings_module = "settings"\n'
    )
    (path / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (path / "test_consumer.py").write_text(textwrap.dedent(tests))


def test_positional_transaction_argument_enables_committed_access(
    tmp_path: Path,
) -> None:
    _project(
        tmp_path,
        """
        from django.db import connection
        from rustest import mark

        @mark.django_db(True)
        def test_committed_access():
            assert not connection.in_atomic_block
    """,
    )
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@parametrize(
    "arguments",
    [
        "transacton=True",
        "True, transaction=False",
        "False, False, None, False, None, True",
    ],
)
def test_invalid_db_marker_arguments_fail_clearly(
    tmp_path: Path, arguments: str
) -> None:
    _project(
        tmp_path,
        f"""
        from rustest import mark

        @mark.django_db({arguments})
        def test_invalid():
            raise AssertionError("test body must not run")
    """,
    )
    result = run_rustest(tmp_path)
    assert result.returncode != 0
    assert "rustest-django: invalid @mark.django_db arguments" in result.stderr
    assert "test body must not run" not in result.stderr


def test_live_server_serves_real_http_and_url_helpers(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from urllib.request import urlopen

        def test_http(live_server):
            assert str(live_server) == live_server.url
            with urlopen(live_server + "/hello/", timeout=5) as response:
                assert response.status == 200
                assert response.read() == b"hello from django"
    """,
    )
    with (tmp_path / "settings.py").open("a") as settings:
        settings.write('ROOT_URLCONF = "urls"\n')
    (tmp_path / "urls.py").write_text(
        textwrap.dedent("""
        from django.http import HttpResponse
        from django.urls import path

        def hello(request):
            return HttpResponse("hello from django")

        urlpatterns = [path("hello/", hello)]
    """)
    )
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def _database_app(path: Path) -> None:
    app = path / "store"
    app.mkdir()
    (app / "__init__.py").write_text("")
    (app / "models.py").write_text(
        textwrap.dedent("""
        from django.db import models

        class Item(models.Model):
            name = models.CharField(max_length=50)
    """)
    )
    with (path / "settings.py").open("a") as settings:
        settings.write('INSTALLED_APPS = ["store"]\nROOT_URLCONF = "urls"\n')
    (path / "urls.py").write_text(
        textwrap.dedent("""
        from django.http import HttpResponse
        from django.urls import path
        from store.models import Item

        def items(request):
            if request.method == "POST":
                Item.objects.create(name="server-created")
            return HttpResponse(",".join(Item.objects.values_list("name", flat=True)))

        urlpatterns = [path("items/", items)]
    """)
    )


def test_live_server_shares_committed_data_and_flushes_between_tests(
    tmp_path: Path,
) -> None:
    _project(
        tmp_path,
        """
        from urllib.request import Request, urlopen
        from django.db import connection
        from rustest import parametrize
        from store.models import Item

        @parametrize("iteration", [1, 2])
        def test_roundtrip(live_server, iteration):
            assert not connection.in_atomic_block
            assert Item.objects.count() == 0
            Item.objects.create(name="test-created")
            with urlopen(live_server + "/items/", timeout=5) as response:
                assert response.read() == b"test-created"
            request = Request(live_server + "/items/", data=b"", method="POST")
            with urlopen(request, timeout=5) as response:
                assert response.read() == b"test-created,server-created"
            assert Item.objects.get(name="server-created").name == "server-created"
    """,
    )
    _database_app(tmp_path)
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_live_server_can_be_used_during_dependent_fixture_setup(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from urllib.request import Request, urlopen
        from rustest import fixture
        from store.models import Item

        @fixture
        def browser_seed(live_server):
            request = Request(live_server + "/items/", data=b"", method="POST")
            with urlopen(request, timeout=5) as response:
                assert response.read() == b"server-created"
            return Item.objects.count()

        def test_fixture_can_request_server(browser_seed):
            assert browser_seed == 1
    """,
    )
    _database_app(tmp_path)
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_serialized_fixture_restores_migration_data_with_other_db_requests(
    tmp_path: Path,
) -> None:
    _project(
        tmp_path,
        """
        from urllib.request import urlopen
        from rustest import parametrize
        from store.models import Item

        def test_flush_first(transactional_db):
            assert Item.objects.get(name="migration-seed").name == "migration-seed"

        @parametrize("iteration", [1, 2])
        def test_restore(
            live_server, db, transactional_db, django_db_serialized_rollback, iteration
        ):
            assert list(Item.objects.values_list("name", flat=True)) == [
                "migration-seed"
            ]
            with urlopen(live_server + "/items/", timeout=5) as response:
                assert response.read() == b"migration-seed"
            Item.objects.create(name="temporary")

        @parametrize("iteration", [1, 2])
        def test_restore_reverse(
            django_db_serialized_rollback, transactional_db, db, live_server, iteration
        ):
            assert list(Item.objects.values_list("name", flat=True)) == [
                "migration-seed"
            ]
            with urlopen(live_server + "/items/", timeout=5) as response:
                assert response.read() == b"migration-seed"
    """,
    )
    _database_app(tmp_path)
    migrations = tmp_path / "store" / "migrations"
    migrations.mkdir()
    (migrations / "__init__.py").write_text("")
    (migrations / "0001_initial.py").write_text(
        textwrap.dedent("""
        from django.db import migrations, models

        def seed(apps, schema_editor):
            apps.get_model("store", "Item").objects.create(name="migration-seed")

        class Migration(migrations.Migration):
            initial = True
            dependencies = []
            operations = [
                migrations.CreateModel(name="Item", fields=[
                    ("id", models.AutoField(primary_key=True)),
                    ("name", models.CharField(max_length=50)),
                ]),
                migrations.RunPython(seed, migrations.RunPython.noop),
            ]
    """)
    )
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_database_suffix_hook_composes_tox_and_worker_names(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        import os
        os.environ["TOX_PARALLEL_ENV"] = "py312"
        os.environ["RUSTEST_DJANGO_DB_SUFFIX"] = "worker2"
        from django.conf import settings

        def test_names(django_db_modify_db_settings):
            databases = settings.DATABASES
            assert databases["default"]["TEST"]["NAME"] == "test_catalog_py312_worker2"
            assert databases["explicit"]["TEST"]["NAME"] == "chosen_py312_worker2"
            assert databases["mirror"]["TEST"]["NAME"] == "mirror-original"
            assert databases["memory"]["TEST"]["NAME"] == ":memory:"
            assert "NAME" not in databases["sqlite"].get("TEST", {})
            assert databases["uri"]["TEST"]["NAME"] == (
                "file:shared?mode=memory&cache=shared"
            )
    """,
    )
    with (tmp_path / "settings.py").open("a") as settings:
        settings.write(
            textwrap.dedent("""
            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.postgresql", "NAME": "catalog"
                },
                "explicit": {
                    "ENGINE": "django.db.backends.postgresql", "NAME": "catalog",
                    "TEST": {"NAME": "chosen"},
                },
                "mirror": {
                    "ENGINE": "django.db.backends.postgresql", "NAME": "catalog",
                    "TEST": {"MIRROR": "default", "NAME": "mirror-original"},
                },
                "memory": {
                    "ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:",
                    "TEST": {"NAME": ":memory:"},
                },
                "sqlite": {
                    "ENGINE": "django.db.backends.sqlite3", "NAME": "production.sqlite3"
                },
                "uri": {
                    "ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:",
                    "TEST": {"NAME": "file:shared?mode=memory&cache=shared"},
                },
            }
        """)
        )
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_session_browser_can_share_live_server_between_isolated_tests(
    tmp_path: Path,
) -> None:
    _project(
        tmp_path,
        """
        from urllib.request import Request, urlopen
        from rustest import fixture, parametrize
        from store.models import Item

        @fixture(scope="session")
        def browser(live_server):
            return live_server.url

        @parametrize("iteration", [1, 2])
        def test_browser(browser, iteration):
            assert Item.objects.count() == 0
            Item.objects.create(name="test-created")
            with urlopen(browser + "/items/", timeout=5) as response:
                assert response.read() == b"test-created"
    """,
    )
    _database_app(tmp_path)
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_failed_live_server_test_restores_database_and_host_scope(
    tmp_path: Path,
) -> None:
    _project(
        tmp_path,
        """
        from urllib.request import Request, urlopen
        from django.conf import settings
        from django.db import connection
        from rustest import raises
        from store.models import Item

        def test_failing_browser(live_server):
            request = Request(live_server + "/items/", data=b"", method="POST")
            with urlopen(request, timeout=5) as response:
                assert response.read() == b"server-created"
            raise AssertionError("expected browser failure")

        def test_unrelated_test_remains_blocked():
            with raises(RuntimeError):
                connection.ensure_connection()
            assert "localhost" not in settings.ALLOWED_HOSTS

        def test_browser_after_failure(live_server):
            assert Item.objects.count() == 0
            with urlopen(live_server + "/items/", timeout=5) as response:
                assert response.read() == b""
    """,
    )
    _database_app(tmp_path)
    result = run_rustest(tmp_path)
    assert result.returncode != 0
    assert "2 passed" in result.stderr, result.stdout + result.stderr
    assert "1 failed" in result.stderr, result.stdout + result.stderr
    assert "expected browser failure" in result.stderr


def test_live_server_serves_static_and_media_files(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from urllib.request import urlopen

        def test_assets(live_server):
            with urlopen(live_server + "/static/sample.txt", timeout=5) as response:
                assert response.read() == b"static asset"
            with urlopen(live_server + "/media/upload.txt", timeout=5) as response:
                assert response.read() == b"uploaded asset"
    """,
    )
    (tmp_path / "urls.py").write_text("urlpatterns = []\n")
    static = tmp_path / "static"
    static.mkdir()
    (static / "sample.txt").write_text("static asset")
    media = tmp_path / "media"
    media.mkdir()
    (media / "upload.txt").write_text("uploaded asset")
    with (tmp_path / "settings.py").open("a") as settings:
        settings.write('INSTALLED_APPS = ["django.contrib.staticfiles"]\n')
        settings.write('ROOT_URLCONF = "urls"\nSTATIC_URL = "/static/"\n')
        settings.write(f"STATICFILES_DIRS = [{str(static)!r}]\n")
        settings.write(f'MEDIA_URL = "/media/"\nMEDIA_ROOT = {str(media)!r}\n')
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_autouse_browser_fixture_receives_transactional_live_server(
    tmp_path: Path,
) -> None:
    _project(
        tmp_path,
        """
        from urllib.request import Request, urlopen
        from rustest import fixture, parametrize
        from store.models import Item

        @fixture(autouse=True)
        def browser_seed(live_server):
            request = Request(live_server + "/items/", data=b"", method="POST")
            with urlopen(request, timeout=5) as response:
                assert response.read() == b"server-created"

        @parametrize("iteration", [1, 2])
        def test_seeded(iteration):
            assert Item.objects.get(name="server-created").name == "server-created"
    """,
    )
    _database_app(tmp_path)
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_db_requests_preserve_flags_when_a_dependency_builds_isolation(
    tmp_path: Path,
) -> None:
    _project(
        tmp_path,
        """
        from urllib.request import urlopen
        from rustest import fixture
        from store.models import Item

        @fixture
        def records(admin_user):
            assert admin_user.is_superuser
            Item.objects.create(name="fixture-created")
            return "fixture-created"

        def test_combined(
            records, transactional_db, django_db_serialized_rollback, live_server
        ):
            with urlopen(live_server + "/items/", timeout=5) as response:
                assert response.read() == b"fixture-created"
    """,
    )
    _database_app(tmp_path)
    with (tmp_path / "settings.py").open("a") as settings:
        settings.write(
            'INSTALLED_APPS = ["django.contrib.auth", '
            '"django.contrib.contenttypes", "store"]\n'
        )
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_cached_session_server_can_start_in_a_later_test(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from urllib.request import urlopen
        from rustest import fixture
        from store.models import Item

        @fixture(scope="session")
        def browser(live_server):
            return live_server

        def test_cache_without_starting_server(browser):
            Item.objects.create(name="first-test")

        def test_first_http_request_uses_current_test(browser):
            assert Item.objects.count() == 0
            Item.objects.create(name="second-test")
            with urlopen(browser + "/items/", timeout=5) as response:
                assert response.read() == b"second-test"
    """,
    )
    _database_app(tmp_path)
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_failed_browser_setup_removes_file_test_database(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from urllib.request import urlopen
        from rustest import fixture

        @fixture
        def broken_browser(live_server):
            with urlopen(live_server + "/items/", timeout=5) as response:
                assert response.read() == b""
            raise RuntimeError("expected browser setup failure")

        def test_browser(broken_browser):
            raise AssertionError("test body must not run")
    """,
    )
    _database_app(tmp_path)
    database = tmp_path / "test.sqlite3"
    with (tmp_path / "settings.py").open("a") as settings:
        settings.write(
            f'DATABASES["default"]["TEST"] = {{"NAME": {str(database)!r}}}\n'
        )
    result = run_rustest(tmp_path)
    assert result.returncode != 0
    assert "expected browser setup failure" in result.stderr
    assert "test body must not run" not in result.stderr
    assert not database.exists(), "The failed session left its test database behind"


def test_usefixtures_marker_enables_transactional_database(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from django.db import connection
        from rustest import mark
        from store.models import Item

        @mark.usefixtures("transactional_db")
        def test_committed_access():
            assert not connection.in_atomic_block
            Item.objects.create(name="marker-created")
            assert Item.objects.get(name="marker-created").name == "marker-created"
    """,
    )
    _database_app(tmp_path)
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_overridden_live_server_does_not_enable_django_database(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from django.conf import settings
        from django.db import connection
        from rustest import raises

        def test_external_server(live_server):
            assert live_server == "https://external.example"
            assert settings.ALLOWED_HOSTS == ["testserver"]
            assert connection.settings_dict["NAME"] == ":memory:"
            with raises(RuntimeError):
                connection.ensure_connection()
    """,
    )
    (tmp_path / "conftest.py").write_text(
        textwrap.dedent("""
        from rustest import fixture
        rustest_fixtures = ["rustest_django"]

        @fixture(scope="session")
        def live_server():
            return "https://external.example"
    """)
    )
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_parametrized_database_fixture_name_is_plain_test_data(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from django.db import connection
        from rustest import mark, parametrize

        @mark.django_db()
        @parametrize("transactional_db", ["label"])
        def test_atomic_data(transactional_db):
            assert transactional_db == "label"
            assert connection.in_atomic_block
    """,
    )
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_stacked_usefixtures_markers_keep_all_database_requests(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from django.db import connection
        from rustest import mark
        from store.models import Item

        @mark.usefixtures("client")
        @mark.usefixtures("transactional_db")
        def test_committed_access():
            assert not connection.in_atomic_block
            Item.objects.create(name="stacked-marker")
            assert Item.objects.get(name="stacked-marker").name == "stacked-marker"
    """,
    )
    _database_app(tmp_path)
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_indirect_database_parametrization_remains_a_fixture(tmp_path: Path) -> None:
    _project(
        tmp_path,
        """
        from django.db import connection
        from rustest import mark, parametrize

        @mark.django_db()
        @parametrize("transactional_db", ["label"], indirect=True)
        def test_committed_fixture(transactional_db):
            assert transactional_db is None
            assert not connection.in_atomic_block
    """,
    )
    result = run_rustest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
