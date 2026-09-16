def test_lifecycle_fixtures_reflect_default_config(
    django_db_keepdb: bool,
    django_db_createdb: bool,
    django_db_use_migrations: bool,
) -> None:
    assert django_db_keepdb is False
    assert django_db_createdb is False
    assert django_db_use_migrations is True
