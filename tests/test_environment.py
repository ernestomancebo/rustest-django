from django.core import mail


def test_mail_outbox_exists_once_test_environment_is_set_up() -> None:
    assert hasattr(mail, "outbox")
