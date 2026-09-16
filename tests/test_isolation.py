from dbapp.models import Thing
from django.db import connection
from rustest import parametrize, raises


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
