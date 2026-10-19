---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Use `rustest-django-doctor`. We upgraded to the rustest-django feature set that
implements live_server, standalone serialized rollback, app isolation, URL overrides,
and template-error exemptions. An old migration note still says all of these are
unsupported. Is that advice current?

Our migrations create a USD currency row. This browser test needs real transaction
commits and must see that row even after another transactional test flushed the tables:

```python
from shop.models import Currency


def test_currency_in_browser(live_server, django_db_serialized_rollback):
    assert Currency.objects.get(code="USD").enabled
    assert str(live_server).startswith("http://")
```

Should we replace these fixtures with db or transactional_db? Explain the transaction
and restoration behavior, and distinguish an error from an older installed version
from a limitation of the current plugin. We cannot run commands in this environment.
