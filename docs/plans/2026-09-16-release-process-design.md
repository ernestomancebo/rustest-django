# Release process design

Tracks: [#23](https://github.com/ernestomancebo/rustest-django/issues/23)
Manual follow-up: [#28](https://github.com/ernestomancebo/rustest-django/issues/28) (PyPI
trusted publisher registration — needs a human with PyPI account access)

## Decisions

- **Versioning**: independent SemVer. `rustest-django` does not mirror pytest-django's
  version numbers — the two projects don't release in lockstep and feature coverage
  isn't 1:1. Compatibility is documented as "ported against pytest-django X.Y", not
  encoded in the version number.
- **Version source**: dynamic, derived from the git tag via `hatch-vcs`. `pyproject.toml`
  drops its static `version = "..."` field entirely (`dynamic = ["version"]` instead),
  so there's no separate declared version that can drift from the tag.
- **Release trigger**: publishing a GitHub Release (`on: release: types: [published]`).
  One button click (or `gh release create`), no local publish commands.
- **Pre-releases**: supported for free via SemVer pre-release tags (`v1.0.0-rc1`, etc.).
  `packaging.version` (used by `hatch-vcs` for normalization) accepts the hyphenated
  form and produces a clean PEP 440 version (`1.0.0rc1`) with no local-version suffix,
  so PyPI accepts it. `pip install rustest-django` won't resolve to a pre-release
  unless `--pre` or an exact version pin is used — safe by pip's own default behavior.
- **No manual-approval gate** on the publish workflow, kept simple deliberately. Every
  published GitHub Release triggers an automatic publish. Worth revisiting later if
  this ever causes a real incident, not preemptively.
- **CI must have passed for the released commit** before publishing proceeds (see
  "release.yml" below) — this is the safety check we do keep.
- **PyPI trust scoping**: the trusted-publisher registration (manual, PyPI-side, see
  #28) is scoped to a GitHub Actions environment named `pypi` — no protection rules
  attached (no approval friction), just a tighter trust boundary than trusting the
  whole repo.

## Components

### `pyproject.toml` changes

- Add `hatch-vcs` to `[build-system].requires`.
- Remove `version = "0.1.0"`; add `dynamic = ["version"]`.
- Add `[tool.hatch.version]` with `source = "vcs"`.
- Local dev is unaffected except that `rustest_django.__version__` will show a
  dev-snapshot version until the first tag exists (nothing reads it for correctness).

### `.github/workflows/release-drafter.yml` + `.github/release-drafter.yml`

Maintains a perpetual **draft** release with an auto-generated, categorized changelog,
and auto-labels PRs. Two jobs:

- `update_release_draft`: on push to `main`. Needs `contents: write`.
- `autolabeler`: on `pull_request: [opened, reopened, synchronize]`. Needs
  `pull-requests: write`.

Categories (based on this repo's actual branch/title conventions, not a generic
template — verified against real merged PR history):

| Category | Branch prefixes | Title fallback |
|---|---|---|
| 🚀 Features | `build/`, `examples/` | `^(Add\|Implement\|Wire\|Build\|Introduce)\b` |
| 🐛 Bug Fixes | `fix/`, `bugfix/` | `^Fix\b` |
| 🧰 Maintenance | `housekeeping/`, `research/`, `prototype/` | `^(Update\|Bump\|Remove\|Clean up)\b` |

Each label's `branch` and `title` matchers combine with release-drafter's built-in OR
logic, which gives "branch first, title as fallback" behavior for free — no explicit
priority mechanism needed. Validated against a real case: PR #27 ("Fix stale README
and incomplete Makefile") has a title starting with "Fix" but branch
`housekeeping/readme-makefile` — branch-first resolution correctly files it under
Maintenance instead of Bug Fixes.

`version-resolver` maps categories to SemVer bump level (`feature`/`enhancement` →
minor, `bug`/`fix` → patch, `chore` → patch), so the draft suggests the next version
automatically.

### `.github/workflows/release.yml`

Separate file from `ci.yml` (different trigger, doesn't need to repeat the 58-job
matrix — that already ran on every push to `main` via `ci.yml`'s own `push` trigger).

1. `actions/checkout@v4` with `ref: ${{ github.event.release.tag_name }}` and
   `fetch-depth: 0`. Two corrections from the first draft: `github.sha` on a `release`
   event is documented to be the default branch's tip, *not* the tagged commit — must
   check out the tag explicitly. Full history is needed for `hatch-vcs` to see tags.
2. Resolve the actual commit SHA from the checked-out tag.
3. Verify CI passed for that exact SHA: query
   `gh api repos/${{ github.repository }}/commits/<sha>/check-runs`, fail the job if
   the `build` check-run's conclusion isn't `success`. Uses the `gh` CLI directly, no
   new third-party action.
4. `astral-sh/setup-uv@v10.1.0`, `uv build`.
5. `pypa/gh-action-pypi-publish` — OIDC trusted publishing (`permissions: id-token:
   write`), targeting the `pypi` environment. No stored PyPI credentials.

No re-run of the test suite or `twine check`/fresh-venv-install here — that already
happened as a required check before merge and again on `main`'s own CI run for this
commit (which step 3 verifies).

## Open item

[#28](https://github.com/ernestomancebo/rustest-django/issues/28): registering the
PyPI trusted publisher itself is a manual, PyPI-account-only step. The workflow can be
built and merged before this is done; it just can't successfully publish until it is.
