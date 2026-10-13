---
type: llm
weight: 1
---

PASS if the response recommends the supported `db` fixture, explains that rollback
isolation preserves migration-loaded reference data between tests, and explains that
`transactional_db` flushes the tables and therefore cannot preserve those rows.

FAIL if the response recommends `transactional_db` as a drop-in replacement, claims
it restores migration data, invents a supported serialized-rollback fixture, or
recommends reloading rows when the requested rollback alternative is sufficient.

This case also checks that the doctor skill's documented workaround is usable.
FAIL if the response reports that the skill incorrectly recommends `transactional_db`
and it had to correct that advice. A model independently repairing the instruction
still exposes a defect in the skill.
