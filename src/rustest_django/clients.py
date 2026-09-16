from __future__ import annotations

import django.test
from rustest import FixtureRequest, fixture


@fixture
def client() -> django.test.Client:
    return django.test.Client()


@fixture
def rf() -> django.test.RequestFactory:
    return django.test.RequestFactory()


@fixture
def async_client() -> django.test.AsyncClient:
    return django.test.AsyncClient()


@fixture
def async_rf() -> django.test.AsyncRequestFactory:
    return django.test.AsyncRequestFactory()


@fixture
def django_user_model(db):
    from django.contrib.auth import get_user_model

    return get_user_model()


@fixture
def django_username_field(django_user_model) -> str:
    return django_user_model.USERNAME_FIELD


@fixture
def admin_user(
    request: FixtureRequest, db, django_user_model, django_username_field: str
):
    # admin_user queries the database from its own body, before the test body
    # runs, so it can't wait for the autouse isolation fixture's normal timing
    # (after every explicit fixture's setup) -- it must force it now.
    request.getfixturevalue("_django_db_isolation")
    user_model = django_user_model
    username_field = django_username_field
    username = "admin@example.com" if username_field == "email" else "admin"

    try:
        user = user_model._default_manager.get_by_natural_key(username)
    except user_model.DoesNotExist:
        user_data = {}
        if "email" in user_model.REQUIRED_FIELDS:
            user_data["email"] = "admin@example.com"
        user_data["password"] = "password"  # noqa: S105 -- pytest-django's own default
        user_data[username_field] = username
        user = user_model._default_manager.create_superuser(**user_data)
    return user


@fixture
def admin_client(db, admin_user) -> django.test.Client:
    admin_client = django.test.Client()
    admin_client.force_login(admin_user)
    return admin_client
