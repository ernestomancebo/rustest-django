SECRET_KEY = "spike"
INSTALLED_APPS = ["blog"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
ROOT_URLCONF = "urls"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
