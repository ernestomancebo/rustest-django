---
type: llm
weight: 1
---

This file hits four of the explicitly-undocumented gaps at once: `fixtures = [...]`,
`setUpTestData`, `addCleanup`, and `subTest`. A successful response:

- Explicitly calls out all four as gaps with no confirmed rustest-django equivalent,
  rather than silently inventing a confident-looking fixture/decorator for each one.
- For `fixtures = [...]`: suggests `call_command("loaddata", ...)` rather than a fake
  rustest-django loader fixture.
- For `setUpTestData`: raises the class-scoped-setup question (move into each test vs. a
  genuinely shared fixture) rather than pretending there's a drop-in equivalent.
- For `addCleanup`: suggests plain code or a fixture's own yield-then-cleanup teardown,
  not an invented `addCleanup`-alike API.
- For `subTest`: suggests parametrizing the test function instead of looping with
  `subTest`, not a fabricated sub-test reporting mechanism.
- Still correctly handles the parts that ARE solved: rewriting to plain functions using
  the `db` fixture, and not silently keeping the `TestCase` subclass.

A failing response confidently rewrites `setUpTestData`/`addCleanup`/`subTest`/
`fixtures` into something that looks plausible but doesn't actually exist in
rustest-django, or simply drops them from the rewrite without comment.
