import django.test


async def test_async_rf_is_an_async_request_factory(async_rf) -> None:
    assert isinstance(async_rf, django.test.AsyncRequestFactory)
    request = async_rf.get("/")
    assert request.path == "/"


async def test_async_client_is_an_async_client(async_client) -> None:
    assert isinstance(async_client, django.test.AsyncClient)
