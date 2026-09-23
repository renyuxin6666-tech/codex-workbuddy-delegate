"""Summarize a frozen A/B experiment from adjudicated, de-identified CSV rows.

This script never reads Codex session logs or provider credentials.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import random
import re
import statistics
import sys

REQUIRED = {
    "task_id", "arm", "task_type", "order", "corpus_sha256", "route_status",
    "codex_model", "codex_reasoning_effort", "plugin_commit", "run_date_utc",
    "codex_input_tokens", "codex_output_tokens",
    "codex_cached_input_tokens", "workbuddy_model", "workbuddy_input_tokens",
    "workbuddy_output_tokens", "workbuddy_credits", "cache_hit", "elapsed_seconds",
    "quality_score", "workbuddy_draft_score", "codex_corrections_count",
    "critical_error", "artifact_sha256", "notes",
}


def number(value: str, name: str, *, minimum: float = 0, maximum: float | None = None) -> float | None:
    if not value.strip():
        return None
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric or blank") from exc
    if not minimum <= result or (maximum is not None and result > maximum):
        raise ValueError(f"{name} outside allowed range")
    return result


def bootstrap_median_interval(values: list[float]) -> list[float] | None:
    if len(values) != 12:
        return None
    generator = random.Random(20260923)
    medians = sorted(statistics.median(generator.choices(values, k=12)) for _ in range(10_000))
    return [medians[250], medians[9749]]


def read_controls(path: Path) -> tuple[str, list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"control_id", "scenario", "expected_decision", "observed_decision", "request_sent", "notes"}
        if not reader.fieldnames or required - set(reader.fieldnames):
            raise ValueError(f"missing routing control columns: {sorted(required - set(reader.fieldnames or []))}")
        rows = list(reader)
    expected = {"NC01": "codex", "NC02": "blocked", "NC03": "blocked", "NC04": "codex"}
    if len(rows) != 4 or {row["control_id"] for row in rows} != set(expected):
        raise ValueError("routing controls must contain NC01–NC04 exactly once")
    issues = []
    incomplete = False
    unsafe = False
    for row in rows:
        control = row["control_id"]
        if row["expected_decision"] != expected[control]:
            raise ValueError(f"{control}: expected decision was changed")
        if not row["observed_decision"] or not row["request_sent"]:
            incomplete = True
            issues.append(f"{control}: routing observation missing")
        elif row["observed_decision"] != expected[control] or row["request_sent"] != "false":
            unsafe = True
            issues.append(f"{control}: unexpected route or model request")
    return ("unsafe" if unsafe else "incomplete" if incomplete else "passed"), issues


def analyze(path: Path, controls_path: Path) -> dict:
    control_status, control_issues = read_controls(controls_path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or REQUIRED - set(reader.fieldnames):
            raise ValueError(f"missing CSV columns: {sorted(REQUIRED - set(reader.fieldnames or []))}")
        rows = list(reader)
    pairs: dict[str, dict[str, dict]] = {}
    for row in rows:
        task, arm = row["task_id"].strip(), row["arm"].strip()
        if not task or arm not in {"A", "B"}:
            raise ValueError("each row needs a task_id and arm A or B")
        if arm in pairs.setdefault(task, {}):
            raise ValueError(f"duplicate {task}/{arm}")
        if row["order"] not in {"AB", "BA"}:
            raise ValueError(f"{task}: order must be AB or BA")
        if row["route_status"] not in {"completed", "blocked", "failed"}:
            raise ValueError(f"{task}: invalid route_status")
        if row["cache_hit"] not in {"true", "false", "unknown"}:
            raise ValueError(f"{task}: cache_hit must be true, false, or unknown")
        if row["critical_error"] not in {"true", "false", "unknown"}:
            raise ValueError(f"{task}: critical_error must be true, false, or unknown")
        if row["task_type"] not in {"extract", "summarize", "classify"}:
            raise ValueError(f"{task}: task_type is outside the frozen design")
        if not row["codex_model"] or not row["codex_reasoning_effort"] or not row["run_date_utc"]:
            raise ValueError(f"{task}: model, reasoning effort and run date must be recorded")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", row["corpus_sha256"]):
            raise ValueError(f"{task}: corpus_sha256 must be a full SHA-256")
        if row["route_status"] == "completed" and not re.fullmatch(r"[0-9a-fA-F]{64}", row["artifact_sha256"]):
            raise ValueError(f"{task}: completed output needs artifact_sha256")
        for field in ("codex_input_tokens", "codex_output_tokens", "codex_cached_input_tokens",
                      "workbuddy_input_tokens", "workbuddy_output_tokens", "workbuddy_credits", "elapsed_seconds"):
            row[field] = number(row[field], field)
        row["quality_score"] = number(row["quality_score"], "quality_score", maximum=100)
        row["workbuddy_draft_score"] = number(row["workbuddy_draft_score"], "workbuddy_draft_score", maximum=100)
        row["codex_corrections_count"] = number(row["codex_corrections_count"], "codex_corrections_count")
        if row["route_status"] != "completed" and row["quality_score"] not in (0, None):
            raise ValueError(f"{task}: failed or blocked run must have quality 0")
        if row["codex_input_tokens"] is not None and row["codex_cached_input_tokens"] is not None:
            if row["codex_cached_input_tokens"] > row["codex_input_tokens"]:
                raise ValueError(f"{task}: cached input exceeds input")
        pairs[task][arm] = row

    if len(pairs) != 12 or any(set(arms) != {"A", "B"} for arms in pairs.values()):
        raise ValueError("locked pilot requires exactly 12 complete A/B task pairs")

    comparisons = []
    issues = []
    for task, arms in sorted(pairs.items()):
        a, b = arms["A"], arms["B"]
        if (a["task_type"], a["order"], a["corpus_sha256"], a["codex_model"], a["codex_reasoning_effort"]) != (
            b["task_type"], b["order"], b["corpus_sha256"], b["codex_model"], b["codex_reasoning_effort"]
        ):
            issues.append(f"{task}: pair conditions differ")
        for arm, row in arms.items():
            if row["quality_score"] is None or row["critical_error"] == "unknown":
                issues.append(f"{task}/{arm}: missing adjudicated quality or critical-error verdict")
            if row["codex_input_tokens"] is None or row["codex_output_tokens"] is None:
                issues.append(f"{task}/{arm}: missing Codex usage")
        if a["route_status"] != "completed":
            issues.append(f"{task}/A: baseline did not complete")
        if a["workbuddy_model"] or a["workbuddy_input_tokens"] is not None or a["workbuddy_output_tokens"] is not None:
            issues.append(f"{task}/A: WorkBuddy contamination")
        if b["route_status"] == "completed" and (b["workbuddy_input_tokens"] is None or b["workbuddy_output_tokens"] is None):
            issues.append(f"{task}/B: missing WorkBuddy usage")
        if b["route_status"] == "completed" and (b["workbuddy_draft_score"] is None or b["codex_corrections_count"] is None):
            issues.append(f"{task}/B: missing worker-draft score or Codex correction count")
        if any(row["elapsed_seconds"] is None for row in arms.values()):
            issues.append(f"{task}: missing elapsed time")
        if b["cache_hit"] != "false":
            issues.append(f"{task}/B: cache contamination or unknown cache status")
        if not b["workbuddy_model"]:
            issues.append(f"{task}/B: WorkBuddy model missing")
        ta = None if a["codex_input_tokens"] is None or a["codex_output_tokens"] is None else (
            a["codex_input_tokens"] + a["codex_output_tokens"]
        )
        tb = None if b["codex_input_tokens"] is None or b["codex_output_tokens"] is None else (
            b["codex_input_tokens"] + b["codex_output_tokens"]
        )
        if ta == 0:
            issues.append(f"{task}/A: zero Codex Token denominator")
        saving = None if not ta or tb is None else (ta - tb) / ta
        quality_delta = None if a["quality_score"] is None or b["quality_score"] is None else (
            b["quality_score"] - a["quality_score"]
        )
        comparisons.append({"task_id": task, "type": a["task_type"], "order": a["order"],
                            "codex_tokens_A": ta, "codex_tokens_B": tb,
                            "codex_saving_fraction": saving, "quality_delta_B_minus_A": quality_delta,
                            "workbuddy_input_tokens": b["workbuddy_input_tokens"],
                            "workbuddy_output_tokens": b["workbuddy_output_tokens"],
                            "workbuddy_credits": b["workbuddy_credits"],
                            "workbuddy_draft_score": b["workbuddy_draft_score"],
                            "codex_corrections_count": b["codex_corrections_count"],
                            "B_completed": b["route_status"] == "completed",
                            "B_critical_error": b["critical_error"]})
    models = {pairs[task]["B"]["workbuddy_model"] for task in pairs}
    if len(models) != 1:
        issues.append("WorkBuddy model changed across tasks")
    plugin_commits = {pairs[task]["B"]["plugin_commit"] for task in pairs}
    if len(plugin_commits) != 1 or not next(iter(plugin_commits)):
        issues.append("plugin commit changed or was not recorded")
    orders = [pairs[task]["A"]["order"] for task in pairs]
    if orders.count("AB") != 6 or orders.count("BA") != 6:
        issues.append("task order is not balanced 6 AB / 6 BA")
    types = [pairs[task]["A"]["task_type"] for task in pairs]
    if any(types.count(kind) != 4 for kind in ("extract", "summarize", "classify")):
        issues.append("task types are not balanced 4/4/4")

    savings = [row["codex_saving_fraction"] for row in comparisons if row["codex_saving_fraction"] is not None]
    deltas = [row["quality_delta_B_minus_A"] for row in comparisons if row["quality_delta_B_minus_A"] is not None]
    med_saving = statistics.median(savings) if len(savings) == 12 else None
    med_delta = statistics.median(deltas) if len(deltas) == 12 else None
    within_five = sum(delta >= -5 for delta in deltas)
    b_completed = sum(row["B_completed"] for row in comparisons)
    b_critical = sum(row["B_critical_error"] == "true" for row in comparisons)
    issues.extend(control_issues)
    if control_status == "unsafe":
        decision = "pilot_no_go"
    elif issues:
        decision = "inconclusive"
    elif med_saving >= .25 and med_delta >= -5 and within_five >= 10 and b_completed >= 11 and b_critical == 0:
        decision = "pilot_go"
    else:
        decision = "pilot_no_go"
    strata = {}
    for kind in ("extract", "summarize", "classify"):
        subset = [row for row in comparisons if row["type"] == kind]
        kind_savings = [row["codex_saving_fraction"] for row in subset if row["codex_saving_fraction"] is not None]
        kind_deltas = [row["quality_delta_B_minus_A"] for row in subset if row["quality_delta_B_minus_A"] is not None]
        strata[kind] = {"pairs": len(subset),
                        "median_codex_saving_fraction": statistics.median(kind_savings) if len(kind_savings) == 4 else None,
                        "median_quality_delta_B_minus_A": statistics.median(kind_deltas) if len(kind_deltas) == 4 else None}
    worker_inputs = [row["workbuddy_input_tokens"] for row in comparisons]
    worker_outputs = [row["workbuddy_output_tokens"] for row in comparisons]
    worker_credits = [row["workbuddy_credits"] for row in comparisons]
    draft_scores = [row["workbuddy_draft_score"] for row in comparisons if row["workbuddy_draft_score"] is not None]
    return {"evidence_status": "pilot", "decision": decision, "pairs": len(comparisons),
            "median_codex_saving_fraction": med_saving, "median_quality_delta_B_minus_A": med_delta,
            "exploratory_bootstrap_95_interval_codex_saving": bootstrap_median_interval(savings),
            "exploratory_bootstrap_95_interval_quality_delta": bootstrap_median_interval(deltas),
            "B_within_5_quality_points": within_five, "B_completed": b_completed,
            "B_critical_errors": b_critical,
            "workbuddy_input_tokens_total": sum(worker_inputs) if all(v is not None for v in worker_inputs) else None,
            "workbuddy_output_tokens_total": sum(worker_outputs) if all(v is not None for v in worker_outputs) else None,
            "workbuddy_credits_total": sum(worker_credits) if all(v is not None for v in worker_credits) else None,
            "median_workbuddy_draft_score": statistics.median(draft_scores) if len(draft_scores) == 12 else None,
            "by_type": strata, "routing_controls": control_status,
            "issues": issues, "per_task": comparisons,
            "claim_boundary": "Local paired pilot only; not total cost or generalized quality."}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python experiment/summarize.py experiment/runs.csv experiment/routing_controls.csv")
    try:
        print(json.dumps(analyze(Path(sys.argv[1]), Path(sys.argv[2])), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Invalid experiment input: {exc}") from exc
