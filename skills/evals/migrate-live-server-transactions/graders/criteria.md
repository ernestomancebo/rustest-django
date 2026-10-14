---
type: llm
weight: 1
---

Grade the proposed complete test file and its explanation.

PASS when it rewrites to a top-level function, preserves both HTTP assertions and
the Currency lookup/save, and replaces self.live_server_url with the supported
live_server address. The test must request live_server and either request
django_db_serialized_rollback or use a function-level django_db marker with
transaction=True and serialized_rollback=True. Either restoration form is valid.
It explains that server-thread visibility needs committed writes and restoration
keeps migration-created rows available after earlier transactional flushes.

FAIL if it retains a Django TestCase subclass, drops real HTTP in favor of only
the Django client, loses a check, omits data restoration, uses atomic db isolation
as the transaction solution, invents a server API, or claims live_server is unsupported.
An execution caveat is acceptable; claims that tests ran must have tool evidence.
