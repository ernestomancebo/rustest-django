# Docs site: MkDocs Material + Read the Docs

Expands GitHub issue #22 ("Write the consumer migration guide") into a full
user-facing documentation site, published on readthedocs.io.

## Tooling & repo layout

- **MkDocs + Material**, added as a new `docs` dependency group in
  `pyproject.toml` (`mkdocs`, `mkdocs-material`), separate from the
  existing `dev` group since most contributors won't need to build docs
  locally.
- New `site-docs/` directory holds all site source Markdown.
  `docs/` (spec, adr, plans) is untouched -- it stays internal, written
  for build sessions, not consumers. The new site's content is written
  fresh for consumers rather than reusing spec language, though it may
  link to `docs/spec/*` from the repo's own README for anyone who wants
  the full design rationale.
- `mkdocs.yml` at repo root: `docs_dir: site-docs`, `theme: material`
  with light/dark toggle, search, and a code-copy button enabled.
- `site-docs/` structure:
  ```
  site-docs/
    index.md              # what rustest-django is, quick example
    getting-started.md    # install, minimal conftest.py, first test run
    migration-guide.md    # the pytest-django -> rustest-django guide
    reference/
      fixtures.md          # consumer-facing fixture list
      markers.md            # @mark.django_db and friends
      configuration.md      # [tool.rustest-django] keys, env var overrides
      unsupported.md        # what's unsupported and why, with fixes
  ```
  Nav order: Home -> Getting Started -> Migration Guide -> Reference.
- Makefile gets a `docs` target: `uv run --group docs mkdocs serve`.

## Read the Docs integration + CI

- New `.readthedocs.yaml`: `mkdocs.yml` as the build config, Python
  pinned to a version in the supported range, dependency install via the
  `docs` group.
- New job in `.github/workflows/ci.yml`: `mkdocs build --strict`, so a
  broken internal link or nav reference fails CI instead of silently
  404ing on the published site.
- No versioned-docs (RTD's stable/latest multi-version builder) for now
  -- single default version, matching the project's pre-1.0 independent
  SemVer stance. Tracked as a separate follow-up issue.
- Registering the project on readthedocs.org needs a human with an RTD
  account (import the repo, connect GitHub) -- same shape as the PyPI
  trusted-publisher step in issue #28. Tracked as a separate issue.

## Migration guide content

`site-docs/migration-guide.md`, in order:

1. **The name swap** -- `pytest_django` -> `rustest_django` import path;
   add `rustest_fixtures = ["rustest_django"]` to `conftest.py`. Two
   paths: rewrite `from pytest_django...` imports directly, or keep
   `import pytest` as-is and pass `--pytest-compat` (trade-offs of each,
   from `docs/spec/api.md`).
2. **Excluding unittest-style tests** -- `SimpleTestCase`/`TestCase`/
   `TransactionTestCase`/`LiveServerTestCase` subclasses fail loudly
   rather than running silently-wrong; how to exclude those paths from
   the rustest run, with the error message from issue #24 as the visible
   signal something needs attention.
3. **A worked before/after example** pulled from `examples/minimal-sqlite`
   -- a real conftest.py and test file, shown pytest-django-style then
   rustest-django-style side by side.
4. **What doesn't migrate** -- pointer to `reference/unsupported.md` for
   `live_server`, `django_isolated_apps`, etc.

## Validation

`mkdocs build --strict` catches broken links/nav in CI. Beyond that, no
automated content tests -- this is prose, reviewed like any PR. Before
merging, the before/after example in migration-guide.md's step 3 is
actually run against both pytest-django and rustest-django to confirm
the shown commands/output are real, not aspirational.
