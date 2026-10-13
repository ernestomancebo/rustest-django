---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

After replacing `pytest.mark.django_db` with the native rustest mark, this plain-function
test is showing up as FAILED under rustest-django. Before the migration, pytest-django
reported it as skipped:

```python
from django.test import skipIfDBFeature
from rustest import mark


@mark.django_db
@skipIfDBFeature("supports_json_field")
def test_json_fallback_path():
    raise AssertionError("This path is only for backends without JSON fields")
```

The test database backend does support JSON fields, so under pytest-django this test was
always skipped, never run. Under rustest-django it now shows up as a failure. How do I
fix this so it goes back to being skipped?
