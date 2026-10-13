---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

We're migrating a Django app's tests from pytest-django to rustest-django. Here's one of
the test files, unchanged so far:

```python
from django.test import TestCase

from blog.models import Post


class PostListTests(TestCase):
    def setUp(self):
        self.post = Post.objects.create(title="visible", published=True)

    def test_list_shows_published_posts(self):
        response = self.client.get("/")
        self.assertContains(response, "visible")

    def test_rejects_unpublished(self):
        Post.objects.create(title="hidden", published=False)
        response = self.client.get("/")
        self.assertNotContains(response, "hidden")
```

What do I need to do to get this file working under rustest-django? Don't rewrite the
file yet, just tell me what's involved.
