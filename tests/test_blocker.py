from django.db import connection
from rustest import raises

from rustest_django.blocker import DjangoDbBlocker


def test_blocked_connection_raises_on_ensure_connection() -> None:
    blocker = DjangoDbBlocker()
    blocker.block()

    with raises(RuntimeError):
        connection.ensure_connection()

    blocker.restore()


def test_unblocked_connection_opens_for_real() -> None:
    blocker = DjangoDbBlocker()
    blocker.unblock()

    connection.ensure_connection()

    assert connection.connection is not None
    blocker.restore()


def test_block_as_context_manager_restores_previous_state_on_exit() -> None:
    blocker = DjangoDbBlocker()
    blocker.unblock()

    with blocker.block(), raises(RuntimeError):
        connection.ensure_connection()

    connection.ensure_connection()
    blocker.restore()


def test_unblock_as_context_manager_restores_block_on_exit() -> None:
    blocker = DjangoDbBlocker()
    blocker.block()

    with blocker.unblock():
        connection.ensure_connection()

    with raises(RuntimeError):
        connection.ensure_connection()

    blocker.restore()


def test_unblock_on_a_fresh_instance_reaches_the_true_original_method() -> None:
    stale_blocker = DjangoDbBlocker()
    stale_blocker.block()  # left blocked on purpose, no restore()

    fresh_blocker = DjangoDbBlocker()
    fresh_blocker.unblock()

    connection.ensure_connection()

    assert connection.connection is not None
    fresh_blocker.restore()
    stale_blocker.restore()


def test_is_active_reflects_pending_block_or_unblock() -> None:
    blocker = DjangoDbBlocker()

    assert blocker.is_active is False

    blocker.block()
    assert blocker.is_active is True

    blocker.restore()
    assert blocker.is_active is False
