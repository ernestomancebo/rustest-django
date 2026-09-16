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
    async_client,
    async_rf,
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
    django_db_createdb,
    django_db_keepdb,
    django_db_modify_db_settings,
    django_db_modify_db_settings_parallel_suffix,
    django_db_modify_db_settings_tox_suffix,
    django_db_modify_db_settings_xdist_suffix,
    django_db_reset_sequences,
    django_db_setup,
    django_db_use_migrations,
    transactional_db,
)
from rustest_django.mail import (  # noqa: E402,F401
    _dj_autoclear_mailbox,
    django_mail_dnsname,
    django_mail_patch_dns,
    mailoutbox,
)
from rustest_django.queries import (  # noqa: E402,F401
    django_assert_max_num_queries,
    django_assert_num_queries,
    django_capture_on_commit_callbacks,
)
from rustest_django.settings_fixture import settings  # noqa: E402,F401
