import os
import tempfile

# docs/spec/async.md: an ORM call wrapped in sync_to_async runs on asgiref's
# executor thread, which may hold a *different* connection than the one the
# isolation opened. An in-memory sqlite database is per-connection, so a
# different connection sees an empty database with no tables at all. A
# file-backed database is shared by every connection that opens the same
# path, sidestepping that entirely.
_DB_PATH = os.path.join(tempfile.gettempdir(), "async_views_example.sqlite3")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _DB_PATH,
    },
}

USE_TZ = True
SECRET_KEY = "example-not-a-real-secret"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "feed",
]

ROOT_URLCONF = "urls"
