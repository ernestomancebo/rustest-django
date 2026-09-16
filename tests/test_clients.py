import django.test


def test_client_is_a_django_test_client(client) -> None:
    assert isinstance(client, django.test.Client)


def test_rf_is_a_django_request_factory(rf) -> None:
    assert isinstance(rf, django.test.RequestFactory)
    request = rf.get("/")
    assert request.path == "/"


def test_django_user_model_is_the_configured_user_model(django_user_model) -> None:
    from django.contrib.auth import get_user_model

    assert django_user_model is get_user_model()


def test_django_username_field_defaults_to_username(django_username_field: str) -> None:
    assert django_username_field == "username"


def test_admin_user_is_a_superuser(admin_user) -> None:
    assert admin_user.username == "admin"
    assert admin_user.is_superuser is True
    assert admin_user.check_password("password") is True


def test_admin_user_reuses_an_existing_admin(admin_user, django_user_model) -> None:
    same_user = django_user_model._default_manager.get_by_natural_key("admin")
    assert same_user.pk == admin_user.pk


def test_admin_client_is_logged_in_as_the_admin_user(admin_client, admin_user) -> None:
    assert int(admin_client.session["_auth_user_id"]) == admin_user.pk
