from dbapp.models import Thing
from rustest import parametrize

from rustest_django import django_db


@django_db(transaction=True)
class TestClassDecoratedIsolation:
    @parametrize("_iteration", [0, 1])
    def test_isolates_between_calls(self, _iteration: int) -> None:
        assert Thing.objects.count() == 0

        Thing.objects.create(name="class-decorated")

        assert Thing.objects.count() == 1

    def helper_not_a_test(self) -> None:
        raise AssertionError("should never be collected or run")
