from django.conf import settings as django_settings


def test_settings_override_takes_effect_and_restores(settings):
    original = django_settings.USE_TZ

    settings.USE_TZ = not original

    assert django_settings.USE_TZ is not original
