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
            }
        },
        USE_TZ=True,
        INSTALLED_APPS=["dbapp"],
    )
    django.setup()

from rustest_django.isolation import (  # noqa: E402,F401
    _django_db_context,
    _django_db_isolation,
    db,
    django_db_blocker,
    django_db_setup,
    transactional_db,
)
