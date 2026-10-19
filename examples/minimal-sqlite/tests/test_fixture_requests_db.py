import pytest

from blog.models import Post


@pytest.fixture
def post_count(db):
    return Post.objects.count()


@pytest.fixture
def post_count_transactional(transactional_db):
    return Post.objects.count()


@pytest.fixture
def seeded_post(db):
    return Post.objects.create(title="seeded")


@pytest.fixture
def seeded_post_transactional(transactional_db):
    return Post.objects.create(title="seeded")


@pytest.fixture
def blocked_probe():
    try:
        Post.objects.count()
    except RuntimeError as exc:
        return exc
    return None


def test_fixture_requesting_db_queries_in_body(post_count):
    assert post_count == 0


def test_fixture_requesting_transactional_db_queries_in_body(
    post_count_transactional,
):
    assert post_count_transactional == 0


@pytest.mark.parametrize("_iteration", [0, 1])
def test_fixture_created_rows_are_rolled_back(seeded_post, _iteration):
    assert Post.objects.count() == 1


@pytest.mark.parametrize("_iteration", [0, 1])
def test_fixture_created_rows_are_flushed(seeded_post_transactional, _iteration):
    assert Post.objects.count() == 1


def test_fixture_without_db_request_stays_blocked(blocked_probe):
    assert isinstance(blocked_probe, RuntimeError)
    assert "Database access not allowed" in str(blocked_probe)


@pytest.fixture
def dynamic_post_count(request):
    request.getfixturevalue("db")
    Post.objects.create(title="dynamic")
    return Post.objects.count()


@pytest.mark.parametrize("_iteration", [0, 1])
def test_fixture_requesting_db_dynamically_queries_in_body(
    dynamic_post_count, _iteration
):
    assert dynamic_post_count == 1
    assert Post.objects.count() == 1
