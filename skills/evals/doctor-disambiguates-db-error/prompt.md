---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

I have two rustest-django test files failing with the exact same error:
`Database access not allowed, use the django_db mark, or the db or transactional_db
fixtures to enable it.`

File A (`tests/test_views.py`), run as `rustest tests/`:

```python
import pytest

from blog.models import Post


@pytest.mark.django_db
def test_post_created(db):
    Post.objects.create(title="x")
```

File B (`tests/test_orders.py`), run as `rustest --pytest-compat tests/`:

```python
from rustest import mark


@mark.django_db
class TestOrders:
    def test_create(self):
        ...

    def test_cancel(self):
        ...
```

Why is each one failing, and what's the actual fix for each? They're not the same
problem even though the error is identical.
