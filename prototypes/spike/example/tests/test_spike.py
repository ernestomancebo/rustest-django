"""Same file runs under pytest + pytest-django and rustest --pytest-compat + the spike."""
import pytest

from blog.models import Post


@pytest.mark.django_db
def test_marker_create():
    Post.objects.create(title="a")
    assert Post.objects.count() == 1


@pytest.mark.django_db
def test_marker_isolated_from_previous():
    assert Post.objects.count() == 0


def test_db_fixture(db):
    Post.objects.create(title="b")
    assert Post.objects.count() == 1


def test_unmarked_is_blocked():
    with pytest.raises(RuntimeError, match="Database access not allowed"):
        Post.objects.count()


@pytest.mark.django_db(transaction=True)
def test_transactional_create():
    Post.objects.create(title="c")
    assert Post.objects.count() == 1


@pytest.mark.django_db
def test_isolated_after_transactional():
    assert Post.objects.count() == 0


def test_client(client, db):
    Post.objects.create(title="d")
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"posts": 1}


def test_rf(rf):
    assert rf.get("/").method == "GET"


@pytest.mark.django_db
def test_deliberate_failure():
    assert Post.objects.count() == 99, "intentional: shows how a failure surfaces"


@pytest.mark.django_db
class TestClassLevelMark:
    def test_method_sees_db(self):
        assert Post.objects.count() == 0
