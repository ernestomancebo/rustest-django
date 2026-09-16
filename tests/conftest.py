import sys
from pathlib import Path

import django
from django.conf import settings

sys.path.insert(0, str(Path(__file__).parent))

if not settings.configured:
    settings.configure(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            },
            "other": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            },
        },
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

from rustest_django.clients import (  # noqa: E402,F401
    admin_client,
    admin_user,
    client,
    django_user_model,
    django_username_field,
    rf,
)
from rustest_django.environment import django_test_environment  # noqa: E402,F401
from rustest_django.isolation import (  # noqa: E402,F401
    _django_db_context,
    _django_db_isolation,
    db,
    django_db_blocker,
    django_db_reset_sequences,
    django_db_setup,
    transactional_db,
)
