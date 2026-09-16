"""Parity oracle: diffs pytest's junit-xml outcomes against rustest's --llm
outcomes for the same example project, failing loudly on any mismatch.

rustest's --llm output only emits individual entries for fail/error/skip
(confirmed via `rustest --llm-schema`) -- passing tests are reflected only in
the aggregate summary counts, never enumerated by id. So a passing outcome
under rustest is *inferred*: any test pytest collected that rustest didn't
report as failed/errored/skipped, provided the total counts reconcile (which
rules out rustest silently missing a test rustest never mentions at all).

Usage: python compare_outcomes.py <pytest-junit.xml> <rustest-llm.jsonl>
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _pytest_outcomes(junit_xml_path: Path) -> dict[str, str]:
    root = ET.parse(junit_xml_path).getroot()
    outcomes: dict[str, str] = {}
    for testcase in root.iter("testcase"):
        classname = testcase.attrib["classname"]
        name = testcase.attrib["name"]
        path = classname.replace(".", "/") + ".py"
        test_id = f"{path}::{name}"

        if testcase.find("failure") is not None:
            outcome = "failed"
        elif testcase.find("error") is not None:
            outcome = "failed"
        elif testcase.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        outcomes[test_id] = outcome
    return outcomes


def _rustest_outcomes(jsonl_path: Path, all_ids: set[str]) -> tuple[dict[str, str], int]:
    non_passing: dict[str, str] = {}
    collection_errors: list[str] = []
    total = None

    for line in jsonl_path.read_text().splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        record = json.loads(line)
        kind = record["t"]
        if kind == "fail":
            non_passing[record["id"]] = "failed"
        elif kind == "skip":
            non_passing[record["id"]] = "skipped"
        elif kind == "error":
            collection_errors.append(record["path"])
        elif kind == "summary":
            total = record["passed"] + record["failed"] + record["skipped"] + record["errors"]

    if total is None:
        raise AssertionError(
            f"{jsonl_path}: no summary line found -- the run was interrupted"
        )
    if collection_errors:
        raise AssertionError(
            f"{jsonl_path}: rustest failed to collect: {collection_errors}"
        )

    outcomes = {test_id: non_passing.get(test_id, "passed") for test_id in all_ids}
    return outcomes, total


def compare(junit_xml_path: Path, jsonl_path: Path) -> None:
    pytest_outcomes = _pytest_outcomes(junit_xml_path)
    rustest_outcomes, rustest_total = _rustest_outcomes(
        jsonl_path, set(pytest_outcomes)
    )

    if len(pytest_outcomes) != rustest_total:
        raise AssertionError(
            f"Collected test count differs: pytest={len(pytest_outcomes)}, "
            f"rustest={rustest_total}"
        )

    mismatches = {
        test_id: (pytest_outcomes[test_id], rustest_outcomes[test_id])
        for test_id in pytest_outcomes
        if pytest_outcomes[test_id] != rustest_outcomes[test_id]
    }
    if mismatches:
        lines = "\n".join(
            f"  {test_id}: pytest={p!r} rustest={r!r}"
            for test_id, (p, r) in sorted(mismatches.items())
        )
        raise AssertionError(f"Outcome mismatch for {len(mismatches)} test(s):\n{lines}")

    print(f"Parity confirmed: {len(pytest_outcomes)} tests, identical outcomes.")


if __name__ == "__main__":
    junit_xml_arg, jsonl_arg = sys.argv[1], sys.argv[2]
    compare(Path(junit_xml_arg), Path(jsonl_arg))
