from dbapp.models import Thing
from django.db import connection
from rustest import fixture, mark, parametrize, raises

from rustest_django.isolation import _DjangoDbContext


@fixture
def _late_transactional_request_error(
    db, _django_db_isolation, _django_db_context: _DjangoDbContext
):
    try:
        _django_db_context.request_transactional()
    except RuntimeError as exc:
        return exc
    return None


@parametrize("_iteration", [0, 1])
def test_db_rolls_back_between_calls(db, _iteration: int) -> None:
    assert Thing.objects.count() == 0

    Thing.objects.create(name="alpha")

    assert Thing.objects.count() == 1


def test_db_not_requested_leaves_access_blocked() -> None:
    with raises(RuntimeError):
        connection.ensure_connection()


@parametrize("_iteration", [0, 1])
def test_transactional_db_flushes_between_calls(
    transactional_db, _iteration: int
) -> None:
    assert Thing.objects.count() == 0

    Thing.objects.create(name="beta")

    assert Thing.objects.count() == 1


@mark.django_db()
@parametrize("_iteration", [0, 1])
def test_django_db_marker_provides_rollback_isolation(_iteration: int) -> None:
    assert Thing.objects.count() == 0

    Thing.objects.create(name="gamma")

    assert Thing.objects.count() == 1


@mark.django_db(transaction=True)
@parametrize("_iteration", [0, 1])
def test_django_db_marker_transaction_kwarg_flushes(_iteration: int) -> None:
    assert Thing.objects.count() == 0

    Thing.objects.create(name="delta")

    assert Thing.objects.count() == 1


@mark.django_db(reset_sequences=True, available_apps=["dbapp"])
def test_django_db_marker_extra_kwargs_do_not_break_isolation() -> None:
    assert Thing.objects.count() == 0

    Thing.objects.create(name="epsilon")

    assert Thing.objects.count() == 1


@parametrize("_iteration", [0, 1])
def test_transactional_db_with_reset_sequences_fixture(
    transactional_db, django_db_reset_sequences, _iteration: int
) -> None:
    assert Thing.objects.count() == 0

    Thing.objects.create(name="zeta")

    assert Thing.objects.count() == 1


@mark.django_db(databases=["default", "other"])
@parametrize("_iteration", [0, 1])
def test_databases_kwarg_isolates_a_second_alias(_iteration: int) -> None:
    assert Thing.objects.using("other").count() == 0

    Thing.objects.using("other").create(name="eta")

    assert Thing.objects.using("other").count() == 1
    assert Thing.objects.count() == 0


@mark.django_db()
def test_default_databases_forbids_the_second_alias() -> None:
    with raises(Exception):
        Thing.objects.using("other").create(name="theta")


def test_flag_requested_after_isolation_built_raises(
    _late_transactional_request_error,
) -> None:
    assert _late_transactional_request_error is not None
    assert "already been built" in str(_late_transactional_request_error)
