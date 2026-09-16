from django.conf import settings as django_settings


def test_settings_override_takes_effect(settings) -> None:
    settings.USE_TZ = False
    assert django_settings.USE_TZ is False


def test_settings_restored_after_previous_test() -> None:
    assert django_settings.USE_TZ is True
