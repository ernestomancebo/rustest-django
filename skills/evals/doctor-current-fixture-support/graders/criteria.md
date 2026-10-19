---
type: llm
weight: 1
---

Evaluate the fixture selection and lifecycle facts for the explicitly stated current
feature set. The five capabilities in the prompt are implemented: that is the API
contract for this case, not a claim the response must verify by executing commands.

PASS when the response:
- Recognizes that all five named capabilities are implemented in the current plugin.
- Keeps live_server and django_db_serialized_rollback for the stated browser test.
- Explains that live_server requires transactional database access, flush can remove
  migration data, and serialized rollback restores that data for a subsequent test.
- Explains that db uses rollback isolation and changes the required commit semantics;
  transactional_db alone does not restore migration data after a flush.
- Treats an old unsupported-feature message as a reason to check the installed
  package/version and fixture registration, without claiming tests were executed.
- Treats fixture parameter order as independent of requested isolation; it should
  not propose reordering fixture arguments as a snapshot-restoration workaround.

FAIL if it calls these features current unsupported gaps, removes the restoration
fixture, substitutes db despite the real-commit requirement, claims transactional_db
alone restores migration data, or recommends reordering fixture arguments to select
isolation. Advice to verify the installation is acceptable. Read/Glob/Grep file
searches and an explanation that no project source is visible are allowed; these do
not claim test execution. A marker example illustrating the equivalent isolation
does not need a whole runnable file: the user requested diagnosis, not a rewrite.
Evaluate the requested fixture decision even when the response also mentions
unrelated known limitations. No release number is required.
