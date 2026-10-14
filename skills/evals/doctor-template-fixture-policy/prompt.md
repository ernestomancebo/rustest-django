---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Use `rustest-django-doctor` with the current plugin. Our configuration enables
`fail_on_template_vars = true`. This test intentionally checks Django's fallback:

```python
from django.template import engines
from rustest import fixture


@fixture
def fallback_html():
    return engines["django"].from_string(
        '{{ missing|default:"fallback" }}'
    ).render({})


def test_intentional_fallback(fallback_html):
    assert fallback_html == "fallback"
```

It fails while the fixture renders the missing variable. Show the complete fix for
this file while leaving strict checking enabled for other tests. Does the fix cover
fixture setup, and does it restore checking after a test or fixture failure? Would a
missing variable inside an `{% if missing %}` conditional fail the same way?
