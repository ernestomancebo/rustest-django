import pytest
from catalog.models import Product


@pytest.mark.django_db
@pytest.mark.parametrize("_iteration", [0, 1])
def test_default_alias_isolates_between_calls(_iteration):
    assert Product.objects.count() == 0

    Product.objects.create(name="widget")

    assert Product.objects.count() == 1


@pytest.mark.django_db(databases=["default", "other"])
@pytest.mark.parametrize("_iteration", [0, 1])
def test_other_alias_isolates_between_calls(_iteration):
    assert Product.objects.using("other").count() == 0

    Product.objects.using("other").create(name="gadget")

    assert Product.objects.using("other").count() == 1
    assert Product.objects.count() == 0


@pytest.mark.django_db
def test_other_alias_is_forbidden_by_default():
    with pytest.raises(Exception, match="other"):
        Product.objects.using("other").create(name="forbidden")


def test_django_db_modify_db_settings_is_usable(django_db_modify_db_settings):
    assert django_db_modify_db_settings is None
