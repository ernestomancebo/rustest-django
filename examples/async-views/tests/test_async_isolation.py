import asyncio

import pytest

from feed.models import Article

_seen_loop_ids: list[int] = []


@pytest.mark.parametrize("_iteration", [0, 1])
async def test_each_async_db_test_gets_a_clean_table_and_its_own_loop(
    transactional_db, _iteration
):
    # docs/spec/async.md: wider loop scopes batching multiple tests onto one
    # event loop is unsupported together with DB fixtures. This is the parity
    # test that turns a rustest scheduler change into a CI failure instead of
    # a consumer's flaky suite: if two calls ever shared a loop, the second
    # id() would collide with the first.
    _seen_loop_ids.append(id(asyncio.get_running_loop()))

    assert await Article.objects.acount() == 0

    await Article.objects.acreate(title="async-article")

    assert await Article.objects.acount() == 1

    if _iteration == 1:
        assert len(set(_seen_loop_ids)) == len(_seen_loop_ids) == 2
