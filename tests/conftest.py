import os
import sys
from pathlib import Path

import django
from django.conf import settings

sys.path.insert(0, str(Path(__file__).parent))


def _start_postgres_container():
    import atexit

    from testcontainers.community.postgres import PostgresContainer

    container = PostgresContainer("postgres:16-alpine", driver="psycopg")
    container.start()
    atexit.register(container.stop)
    return container


def _databases() -> dict[str, dict[str, str]]:
    if os.environ.get("TEST_DB_BACKEND") == "postgres":
        container = _start_postgres_container()
        base = {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": container.get_container_host_ip(),
            "PORT": container.get_exposed_port(5432),
            "USER": container.username,
            "PASSWORD": container.password,
        }
        return {
            "default": {
                **base,
                "NAME": container.dbname,
                "TEST": {"NAME": "test_rustest_django"},
            },
            "other": {
                **base,
                "NAME": container.dbname,
                "TEST": {"NAME": "test_rustest_django_other"},
            },
        }
    return {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
        "other": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
    }


if not settings.configured:
    settings.configure(
        DATABASES=_databases(),
        USE_TZ=True,
        SECRET_KEY="test-secret-key",
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "dbapp",
        ],
    )
    django.setup()

# Same fixture-loading mechanism documented for consumers (see
# site-docs/getting-started.md) -- rustest imports "rustest_django" and picks
# up every @fixture-decorated name rustest_django/__init__.py aggregates.
rustest_fixtures = ["rustest_django"]
