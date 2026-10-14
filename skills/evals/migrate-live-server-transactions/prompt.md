---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Use `rustest-django-migrate-tests` to produce a complete plain-function rewrite of
this test file for the current plugin, which supports live_server and standalone
serialized rollback. Registration, migrations, and the `/currency/` route are already
configured. The route returns the USD Currency row's label as its response body.
An earlier transactional test may flush the tables, and our data migration initially
creates the USD row. Keep real HTTP and committed writes visible to its server thread.

```python
from urllib.request import urlopen

from django.test import LiveServerTestCase
from shop.models import Currency


class CurrencyBrowserTests(LiveServerTestCase):
    serialized_rollback = True

    def test_committed_currency_label(self):
        currency = Currency.objects.get(code="USD")
        currency.label = "US Dollar"
        currency.save()
        with urlopen(self.live_server_url + "/currency/", timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read().decode(), "US Dollar")
```

Include all imports. Do not assume any command can be run in this environment.
