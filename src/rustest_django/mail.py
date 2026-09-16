from __future__ import annotations

from django.core import mail
from rustest import FixtureRequest, fixture


@fixture(autouse=True)
def _dj_autoclear_mailbox():
    if hasattr(mail, "outbox"):
        mail.outbox.clear()


@fixture
def django_mail_dnsname() -> str:
    return "fake-tests.example.com"


@fixture
def django_mail_patch_dns(monkeypatch, django_mail_dnsname: str) -> None:
    monkeypatch.setattr(mail.message, "DNS_NAME", django_mail_dnsname)


@fixture
def mailoutbox(
    request: FixtureRequest, django_mail_patch_dns: None, _dj_autoclear_mailbox: None
):
    # Like admin_user, this reads global state (mail.outbox) that only exists
    # once django_test_environment has run -- but that's session-scoped
    # autouse, which only activates after every explicit fixture (including
    # this one) finishes setup. Force it now instead of waiting.
    request.getfixturevalue("django_test_environment")
    if hasattr(mail, "outbox"):
        return mail.outbox
    return []
