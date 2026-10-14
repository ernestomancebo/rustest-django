---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Help me migrate this test file to rustest-django:

```python
from django.test import TestCase


class OrderTests(TestCase):
    fixtures = ["initial_customers.json"]

    @classmethod
    def setUpTestData(cls):
        cls.shared_order = Order.objects.create(reference="A1")

    def test_total_is_computed(self):
        self.assertEqual(self.shared_order.total, 0)

    def test_cancel_runs_cleanup(self):
        self.addCleanup(lambda: self.shared_order.delete())
        self.shared_order.cancel()
        self.assertTrue(self.shared_order.cancelled)

    def test_status_transitions(self):
        for status in ["pending", "paid", "shipped"]:
            with self.subTest(status=status):
                self.shared_order.status = status
                self.shared_order.save()
                self.assertEqual(self.shared_order.status, status)
```

Go ahead and rewrite it.
