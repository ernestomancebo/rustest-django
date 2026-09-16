import pytest

from blog.models import Post


@pytest.mark.django_db
def test_post_list_shows_published_posts(client):
    Post.objects.create(title="visible", published=True)
    Post.objects.create(title="hidden", published=False)

    response = client.get("/")

    content = response.content.decode()
    assert "visible" in content
    assert "hidden" not in content


def test_rf_builds_a_request(rf):
    request = rf.get("/")

    assert request.path == "/"


@pytest.mark.django_db
def test_post_create_requires_login(client):
    response = client.post("/new/", {"title": "anon post"})

    assert response.status_code == 302
    assert Post.objects.count() == 0


@pytest.mark.django_db
def test_post_create_get_is_not_allowed_when_logged_in(admin_client):
    response = admin_client.get("/new/")

    assert response.status_code == 405
