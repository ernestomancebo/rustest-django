---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Use `rustest-django-migrate-tests` to rewrite this Django test as a complete, runnable
plain-function test file. Follow the skill's assertion-conversion recipe and include
the imports. The project's rustest-django registration is already configured.
If the skill's recipe cannot produce working imports for these checks, explain the
problem rather than silently correcting its instructions.

```python
from django.http import HttpResponse
from django.test import SimpleTestCase


class AssertionTests(SimpleTestCase):
    def test_response(self):
        response = HttpResponse("hello")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content)
        self.assertContains(response, "hello")

    def test_invalid_integer(self):
        with self.assertRaises(ValueError):
            int("invalid")
```
