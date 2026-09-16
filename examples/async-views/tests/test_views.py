from feed.models import Article


async def test_async_rf_builds_a_request(async_rf):
    request = async_rf.get("/")

    assert request.path == "/"


async def test_article_list_shows_articles(transactional_db, async_client):
    await Article.objects.acreate(title="hello async")

    response = await async_client.get("/")

    assert response.status_code == 200
    assert "hello async" in response.content.decode()
