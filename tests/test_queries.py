from dbapp.models import Thing
from rustest import raises


def test_django_assert_num_queries_passes_on_exact_match(
    db, django_assert_num_queries
) -> None:
    with django_assert_num_queries(1):
        Thing.objects.create(name="a")


def test_django_assert_num_queries_fails_on_mismatch(
    db, django_assert_num_queries
) -> None:
    with (
        raises(Exception, match="Expected to perform 2 queries"),
        django_assert_num_queries(2),
    ):
        Thing.objects.create(name="a")


def test_django_assert_max_num_queries_allows_fewer(
    db, django_assert_max_num_queries
) -> None:
    with django_assert_max_num_queries(5):
        Thing.objects.create(name="a")


def test_django_assert_max_num_queries_fails_over_the_limit(
    db, django_assert_max_num_queries
) -> None:
    with (
        raises(Exception, match="Expected to perform 0 queries or less"),
        django_assert_max_num_queries(0),
    ):
        Thing.objects.create(name="a")


def test_django_capture_on_commit_callbacks_captures(
    db, django_capture_on_commit_callbacks
) -> None:
    from django.db import transaction

    calls = []
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        transaction.on_commit(lambda: calls.append("ran"))

    assert calls == ["ran"]
    assert len(callbacks) == 1
