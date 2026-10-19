---
type: llm
weight: 1
---

PASS when the proposed file imports rustest.mark (directly or through the module),
places argument-free @mark.ignore_template_errors or @mark.ignore_template_errors()
on test_intentional_fallback, and keeps the fixture and fallback assertion.
It explains that the exemption covers consumer fixture setup, strict checking is
restored after the marked test including failures, a default filter does not prevent
strict missing-rendered-variable errors, and missing conditional values are allowed.

FAIL if it disables strict checking for the suite, only marks the fixture instead of
the test, invents a marker argument, drops the assertion, or says the exemption is
unsupported or starts after fixture setup. An unexecuted-code caveat is acceptable.
