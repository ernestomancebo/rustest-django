---
type: llm
weight: 1
---

Grade the proposed Python test file. Judge code correctness separately from prose
about whether commands could run. The supported API facts below are authoritative.
Inability to inspect an installed package is not evidence that these imports fail.

PASS if the response gives a complete plain-function rewrite with:

- A Python assertion for status-code equality and for nonempty response content.
- `rustest.raises(ValueError)` (imported directly or through the module) for the
  exception context manager.
- `assertContains` imported from `rustest_django.asserts` for the Django-specific
  response assertion.
- The original checks preserved, without a Django TestCase subclass or `self` calls.

PASS a file satisfying every check above even when surrounding prose says the
imports could not be inspected, the file was not executed, or suggests verifying
them locally. Those caveats do not remove a supplied check or invalidate a confirmed
public import. A complete file using these imports is resolved code.

FAIL if the rewritten file imports or calls `assertEqual`, `assertTrue`, or
`assertRaises` from `rustest_django.asserts`: these inherited unittest methods are
not exported there. Also fail if an original check is omitted, or only a migration
plan is provided instead of the requested runnable file. Mentions of the original
unittest calls in conversion explanations are acceptable; inspect the proposed code
for incorrect imports or remaining self calls.
