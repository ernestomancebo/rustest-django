# PROTOTYPE: rustest-django spike (throwaway)

Answers wayfinder ticket #8: does a rustest fixture module reproduce pytest-django's
core plumbing (session setup, DB blocker, `db`/`transactional_db`, `django_db` marker,
`client`) and where does rustest diverge? Not production code. Lives on branch
`prototype/spike` only.

## Run

From this directory, with a venv holding `rustest django pytest pytest-django`:

```sh
cd example
python -m pytest tests                     # pytest + pytest-django
python -m rustest --pytest-compat tests    # rustest + this spike
```

Expected: both report the same outcome for every test except the ones listed
under "known divergences" in the ticket resolution. `test_deliberate_failure`
fails on purpose under both, to show how a failure surfaces.
