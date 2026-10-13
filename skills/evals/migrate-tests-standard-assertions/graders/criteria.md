---
type: llm
weight: 1
---

PASS if the response gives a complete plain-function rewrite with:

- A Python assertion for status-code equality and for nonempty response content.
- `rustest.raises(ValueError)` (imported directly or through the module) for the
  exception context manager.
- `assertContains` imported from `rustest_django.asserts` for the Django-specific
  response assertion.
- The original checks preserved, without a Django TestCase subclass or `self` calls.

This case also checks that the skill's recipe is usable as written. FAIL if the
response reports that the skill incorrectly tells it to import inherited unittest
assertions and it had to correct that recipe, or leaves the replacement undecided
pending a speculative import check. A model independently repairing incorrect
instructions still exposes a defect in this migration skill.

FAIL if the rewritten file imports or calls `assertEqual`, `assertTrue`, or
`assertRaises` from `rustest_django.asserts`: these inherited unittest methods are
not exported there. Also fail if an original check is omitted, or only a migration
plan is provided instead of the requested runnable file.
