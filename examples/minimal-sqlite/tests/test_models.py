import pytest

from blog.models import Post


@pytest.mark.django_db
@pytest.mark.parametrize("_iteration", [0, 1])
def test_db_rolls_back_between_calls(_iteration):
    assert Post.objects.count() == 0

    Post.objects.create(title="hello")

    assert Post.objects.count() == 1


@pytest.mark.parametrize("_iteration", [0, 1])
def test_transactional_db_flushes_between_calls(transactional_db, _iteration):
    assert Post.objects.count() == 0

    Post.objects.create(title="flushed")

    assert Post.objects.count() == 1
