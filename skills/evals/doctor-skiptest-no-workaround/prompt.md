---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

This test is showing up as FAILED under rustest-django, but it used to pass fine under
pytest-django:

```python
from django.test import TestCase
from django.test.utils import skipIfDBFeature


class FeatureTests(TestCase):
    @skipIfDBFeature("supports_json_field")
    def test_json_fallback_path(self):
        ...
```

The test database backend does support JSON fields, so under pytest-django this test was
always skipped, never run. Under rustest-django it now shows up as a failure. How do I
fix this so it goes back to being skipped?
