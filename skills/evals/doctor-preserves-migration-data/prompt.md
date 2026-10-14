---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Use `rustest-django-doctor` to diagnose this migration problem and follow its
legacy-fixture replacement advice. We are pinned to an older rustest-django release
that predates standalone serialized rollback; upgrading is outside this request.
Our Django migrations create a USD currency
row which these tests need:

```python
from shop.models import Currency


def test_default_currency(django_db_serialized_rollback):
    assert Currency.objects.get(code="USD").enabled
```

rustest-django says `django_db_serialized_rollback` is unsupported. These are plain
test functions, and we do not need explicit transaction commits or flush isolation.
Which supported fixture should replace it so migration-loaded rows survive between
tests? Explain why. If the skill's suggested replacement would lose the rows, say so
rather than silently correcting that advice.
