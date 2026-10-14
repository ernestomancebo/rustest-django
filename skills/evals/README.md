# Skill evaluations

Run the same suite and settings as CI from the repository root:

```bash
python scripts/run_skill_evals.py --trust-plugin --no-publish \
  --ablation with-without --runs 3 --concurrency 3 --judge-model opus \
  --threshold 1.0 --json skills/evals/results/local-ci-run.json
```

The workflow pins Claude Code 2.1.299 and uses an Opus judge, calibrated against
captured answers and intentionally invalid controls. Local runs use the existing
Claude Code authentication; CI supplies `CLAUDE_CODE_OAUTH_TOKEN`.

Eleven cases run three times with the skills and three times without them. The
100% threshold applies to the skill-enabled arm; the baseline measures the skill's
effect. Each LLM grade uses Claude Code's three judge votes.

Claude Code's LLM graders receive the criterion and final answer, without the
original request. The runner prepares a temporary copy of the suite and includes
the original request and current public API references in each LLM criterion.
Explicit older-version constraints still take precedence. Agent prompts, original
criteria, non-LLM graders, repetitions, and baseline arms are preserved. Reports
remain in `skills/evals/results/` after the temporary suite is removed.

To inspect the complete grading inputs without running paid evaluations:

```bash
python scripts/run_skill_evals.py --prepare-only /tmp/rustest-django-eval-inputs
```

Use a destination that does not already exist. Changes to the preparation step are
covered by the consumer CLI test in `tests/test_skill_eval_examples.py`; the template
and app-isolation examples in this suite are also executed there.
