---
status: accepted
---

# Distribute the migration/diagnostic skills via skills.sh, not a dedicated Claude Code plugin

We're shipping `migrate-tests` and `doctor` (agent skills that help a consumer migrate a
Django `TestCase` suite to rustest-django, and diagnose rustest-django-specific failures)
through `skills.sh` rather than as a bespoke Claude Code marketplace plugin. `skills.sh`
already lists Claude Code as one of 15+ supported targets and installs the same
`SKILL.md` format straight into `.claude/skills/`, so a dedicated plugin would be a
second distribution surface for users skills.sh already reaches. We chose the broader,
simpler surface over Claude-Code-specific packaging.

## Consequences

- No plugin namespace to disambiguate skill names, so the `name:` frontmatter field
  itself must be prefixed (`rustest-django-migrate-tests`, `rustest-django-doctor`) to
  avoid colliding with an identically-named skill from an unrelated pack.
- No separate release/packaging step: skills.sh consumers pull the `skills/` directory
  straight from the repo/tag, so shipping a skill update is just landing the change at
  HEAD, same as any other doc.
- No Claude-Code-specific auto-update through its own plugin manager. Revisit a
  dedicated plugin only if that turns out to matter enough on its own to justify a
  second release surface -- not speculatively.
- `skills/.claude-plugin/plugin.json` still exists in the repo despite this decision: it
  is local-only tooling so `claude plugin eval` can identify `skills/` as a plugin for
  CI/local eval runs. It is never published to, or listed on, a Claude Code marketplace --
  don't mistake its presence for a reversal of this decision.
