from blog.models import Post


def test_admin_user_is_a_superuser(admin_user):
    assert admin_user.is_superuser is True


def test_admin_client_can_create_a_post(admin_client):
    response = admin_client.post("/new/", {"title": "from admin", "body": "hi"})

    assert response.status_code == 201
    assert Post.objects.get().title == "from admin"


def test_django_user_model_matches_configured_user_model(django_user_model):
    from django.contrib.auth import get_user_model

    assert django_user_model is get_user_model()
