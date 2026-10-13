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

Grade the proposed test file against the supported imports and checks above. A note
that the file was not executed or the installed package could not be inspected is
acceptable when the complete, correct file is provided. Such a verification caveat
does not make a supported import wrong. Fail an incomplete rewrite or an unresolved
replacement that leaves a check out of the proposed file.

FAIL if the rewritten file imports or calls `assertEqual`, `assertTrue`, or
`assertRaises` from `rustest_django.asserts`: these inherited unittest methods are
not exported there. Also fail if an original check is omitted, or only a migration
plan is provided instead of the requested runnable file.
