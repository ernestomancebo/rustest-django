---
type: llm
weight: 1
---

The user explicitly asks for a plan and says not to rewrite the file yet. Grade the
diagnosis and concrete conversion plan; generated code, file edits, and execution
are not required.

A successful response:

- Identifies that `PostListTests` subclasses Django's `TestCase`, and that this needs a
  full rewrite to plain functions — not just adding a marker or fixture on top of the
  class as-is. It should explain *why*: rustest runs the methods but discards their
  result, so leaving the class as a `TestCase` would silently report passes regardless
  of outcome.
- Gives a concrete rewrite, or a concrete plan for one, that: drops the class in favor of
  top-level test functions; replaces `self.client` with the `client` fixture; replaces
  `self.assertContains`/`self.assertNotContains` with the module-level functions from
  `rustest_django.asserts`; and uses the `db` fixture (directly, or via `@mark.django_db`)
  for database access instead of relying on `TestCase`'s implicit transaction wrapping.
  A primary plan using top-level functions can also mention grouping the converted
  functions into a plain TestCase-free class with @django_db(). That is a supported
  alternative, not keeping the original Django subclass. Judge inheritance, not the
  presence of the word "class" or a class decorator.
- Does not claim this file "just works" under rustest-django with no changes, and does
  not suggest silencing or catching the guard's failure instead of rewriting.

A failing response does any of: proposes keeping the Django `TestCase` subclass with a marker
bolted on; omits the asserts or `self.client` rewrite; or doesn't explain that the guard
fails loudly rather than silently skipping.
