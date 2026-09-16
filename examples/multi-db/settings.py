import os


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
                "TEST": {"NAME": "test_multi_db_default"},
            },
            "other": {
                **base,
                "NAME": container.dbname,
                "TEST": {"NAME": "test_multi_db_other"},
            },
        }
    return {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
        "other": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
    }


DATABASES = _databases()

USE_TZ = True
SECRET_KEY = "example-not-a-real-secret"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "catalog",
]
