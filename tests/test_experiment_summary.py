"""Check that the preregistered gate never hides missing usage or critical errors."""
import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiment"))
from summarize import analyze, REQUIRED


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "runs.csv"
        self.controls_path = Path(self.temp.name) / "routing_controls.csv"
        self.controls = [
            {"control_id": f"NC{index:02}", "scenario": "synthetic",
             "expected_decision": decision, "observed_decision": decision,
             "request_sent": "false", "notes": ""}
            for index, decision in enumerate(("codex", "blocked", "blocked", "codex"), 1)
        ]
        self.rows = []
        for index in range(12):
            kind = ("extract", "summarize", "classify")[index // 4]
            for arm in ("A", "B"):
                self.rows.append({
                    "task_id": f"T{index+1:02}", "arm": arm, "task_type": kind,
                    "order": "AB" if index % 2 == 0 else "BA",
                    "corpus_sha256": "a" * 64, "route_status": "completed",
                    "codex_model": "same-model", "codex_reasoning_effort": "medium",
                    "plugin_commit": "abc123" if arm == "B" else "",
                    "run_date_utc": "2026-09-23T00:00:00Z",
                    "codex_input_tokens": "800" if arm == "B" else "1100",
                    "codex_output_tokens": "200" if arm == "B" else "300",
                    "codex_cached_input_tokens": "100",
                    "workbuddy_model": "fixed-worker" if arm == "B" else "",
                    "workbuddy_input_tokens": "700" if arm == "B" else "",
                    "workbuddy_output_tokens": "100" if arm == "B" else "",
                    "workbuddy_credits": "0.1" if arm == "B" else "",
                    "cache_hit": "false", "elapsed_seconds": "20", "quality_score": "90",
                    "workbuddy_draft_score": "85" if arm == "B" else "",
                    "codex_corrections_count": "1" if arm == "B" else "",
                    "critical_error": "false", "artifact_sha256": "b" * 64, "notes": "",
                })

    def run_summary(self):
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=sorted(REQUIRED))
            writer.writeheader()
            writer.writerows(self.rows)
        with self.controls_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.controls[0]))
            writer.writeheader()
            writer.writerows(self.controls)
        return analyze(self.path, self.controls_path)

    def test_go_and_no_go(self):
        self.assertEqual(self.run_summary()["decision"], "pilot_go")
        self.rows[1]["critical_error"] = "true"
        self.assertEqual(self.run_summary()["decision"], "pilot_no_go")

    def test_missing_worker_usage_is_inconclusive(self):
        self.rows[1]["workbuddy_input_tokens"] = ""
        result = self.run_summary()
        self.assertEqual(result["decision"], "inconclusive")
        self.assertIn("missing WorkBuddy usage", " ".join(result["issues"]))

    def test_unsafe_control_forces_no_go(self):
        self.controls[1]["request_sent"] = "true"
        self.assertEqual(self.run_summary()["decision"], "pilot_no_go")


if __name__ == "__main__":
    unittest.main()
