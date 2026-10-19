---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Use `rustest-django-doctor` for the current plugin. This plain-function test requests
`django_isolated_apps` and fails saying it requires `django_isolate_apps`:

```python
from django.db import models


def test_dynamic_model(django_isolated_apps):
    class Temporary(models.Model):
        class Meta:
            app_label = "contenttypes"

    assert django_isolated_apps.get_model("contenttypes", "Temporary") is Temporary
```

Show a complete corrected file using the installed `django.contrib.contenttypes`
app. Does this registry fixture also create a database table or authorize ORM
queries? We only need model registration. Explain the cleanup behavior and whether
putting the marker on a plain class would cover all its methods.
