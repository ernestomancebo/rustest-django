from django.core import mail as django_mail


def test_mailoutbox_captures_sent_mail(mailoutbox) -> None:
    django_mail.send_mail("subject", "body", "from@example.com", ["to@example.com"])

    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "subject"


def test_mailoutbox_is_cleared_between_tests(mailoutbox) -> None:
    assert len(mailoutbox) == 0


def test_django_mail_patch_dns_sets_dns_name(django_mail_patch_dns) -> None:
    assert django_mail.message.DNS_NAME == "fake-tests.example.com"
