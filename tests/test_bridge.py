from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "workbuddy-delegate" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import workbuddy_bridge as bridge


def worker_result(answer="A useful answer", evidence=None):
    return json.dumps({"answer": answer, "evidence": evidence or [], "uncertainties": []})


def success_event(result="answer"):
    return {
        "type": "result",
        "subtype": "success",
        "result": result,
        "usage": {"input_tokens": 20, "output_tokens": 5},
    }


class IsolatedTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.env = patch.dict(
            os.environ,
            {
                "WORKBUDDY_DELEGATE_CONFIG": str(self.base / "config.json"),
                "WORKBUDDY_DELEGATE_STATE_DIR": str(self.base / "state"),
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)


class ConfigTests(IsolatedTest):
    def test_defaults_and_atomic_save(self):
        self.assertEqual(bridge.load_config()["model"], "auto")
        saved = bridge.save_config({"daily_call_limit": 7})
        self.assertEqual(saved["daily_call_limit"], 7)
        self.assertEqual(json.loads((self.base / "config.json").read_text())["daily_call_limit"], 7)

    def test_invalid_config_is_rejected(self):
        for update in [
            {"daily_call_limit": 0},
            {"max_input_chars": "many"},
            {"allowed_roots": "C:/"},
            {"unknown": True},
        ]:
            with self.subTest(update=update), self.assertRaises(bridge.BridgeError):
                bridge.save_config(update)


class SourceTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()

    def read(self, name):
        return bridge.read_sources(self.workspace, [name], "", 10_000, [str(self.workspace)])

    def test_file_requires_allowed_root(self):
        (self.workspace / "note.txt").write_text("hello", encoding="utf-8")
        with self.assertRaisesRegex(bridge.BridgeError, "allowed_roots"):
            bridge.read_sources(self.workspace, ["note.txt"], "", 10_000, [])
        _, sources = self.read("note.txt")
        self.assertEqual(sources, {"note.txt": "hello"})

    def test_text_only_does_not_require_allowed_root(self):
        _, sources = bridge.read_sources(self.workspace, [], "hello", 10_000, [])
        self.assertEqual(sources, {"provided_text": "hello"})

    def test_parent_absolute_and_sensitive_paths_are_rejected(self):
        outside = self.base / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        for name in ["../outside.txt", str(outside), ".env", ".ssh/config", "credentials.json", "private.key"]:
            target = self.workspace / name
            if not Path(name).is_absolute() and ".." not in Path(name).parts:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("private", encoding="utf-8")
            with self.subTest(name=name), self.assertRaises(bridge.BridgeError):
                self.read(name)

    def test_input_limit_and_duplicates(self):
        (self.workspace / "large.txt").write_text("x" * 101, encoding="utf-8")
        with self.assertRaises(bridge.BridgeError):
            bridge.read_sources(self.workspace, ["large.txt"], "", 100, [str(self.workspace)])
        with self.assertRaises(bridge.BridgeError):
            bridge.read_sources(self.workspace, ["large.txt", "large.txt"], "", 1000, [str(self.workspace)])


class RoutingAndEvidenceTests(unittest.TestCase):
    def test_only_supported_low_risk_work_routes(self):
        for kind in bridge.KINDS:
            self.assertEqual(bridge.plan(kind, "low", "Do it")["route"], "workbuddy")
        for kind, risk in [("summarize", "medium"), ("deploy", "low"), ("summarize", "LOW")]:
            self.assertEqual(bridge.plan(kind, risk, "Do it")["route"], "codex")

    def test_exact_quotes_required_and_checked(self):
        raw = worker_result(evidence=[{"source": "a.txt", "quote": "exact fact"}])
        value = bridge.validate_worker_result(raw, {"a.txt": "An exact fact."}, "extract")
        self.assertEqual(value["answer"], "A useful answer")
        for evidence in [[], [{"source": "a.txt", "quote": "invented"}], [{"source": "b.txt", "quote": "fact"}]]:
            with self.subTest(evidence=evidence), self.assertRaises(bridge.BridgeError):
                bridge.validate_worker_result(worker_result(evidence=evidence), {"a.txt": "fact"}, "summarize")

    def test_answer_limit_matches_worker_prompt(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.validate_worker_result(worker_result(answer="x" * 6001), {}, "rewrite")


class LedgerAndCacheTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()
        self.cfg = {
            "model": "fake-low-cost",
            "max_input_chars": 10_000,
            "cache_hours": 24,
            "daily_call_limit": 20,
            "timeout_seconds": 10,
            "state_dir": str(self.base / "state-override"),
            "allowed_roots": [],
            "retention_days": 30,
            "cli_root": "",
            "node_path": "",
        }
        self.install_patch = patch.object(bridge, "installation", return_value=("node", self.base))
        self.invoke_patch = patch.object(bridge, "invoke", return_value=(worker_result(), {}))
        self.install_patch.start()
        self.invoke = self.invoke_patch.start()
        self.addCleanup(self.install_patch.stop)
        self.addCleanup(self.invoke_patch.stop)

    def run_delegate(self, text="source"):
        return bridge.delegate("Rewrite", self.workspace, kind="rewrite", risk="low", text=text, cfg=self.cfg)

    def test_cache_avoids_duplicate_call(self):
        first, second = self.run_delegate(), self.run_delegate()
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertTrue(second["usage_is_historical"])
        self.assertEqual(self.invoke.call_count, 1)

    def test_daily_limit_blocks_new_request(self):
        self.cfg["daily_call_limit"] = 1
        self.run_delegate()
        with self.assertRaises(bridge.BridgeError):
            self.run_delegate("new")

    def test_concurrent_identical_reservation_is_rejected(self):
        state = self.base / "parallel"
        first = bridge.reserve(state, "same", 5)
        with self.assertRaisesRegex(bridge.BridgeError, "already in progress"):
            bridge.reserve(state, "same", 5)
        bridge.finish(state, first, "completed")

    def test_parallel_limit_never_exceeded(self):
        state = self.base / "parallel-limit"
        def reserve(index):
            try:
                bridge.reserve(state, str(index), 3)
                return True
            except bridge.BridgeError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(reserve, range(12))), 3)

    def test_prune_removes_only_old_result_json(self):
        results = bridge.state_path(self.cfg) / "results"
        results.mkdir(parents=True)
        old = results / "old.json"
        keep = results / "keep.txt"
        old.write_text("{}")
        keep.write_text("keep")
        os.utime(old, (1, 1))
        self.assertEqual(bridge.prune_results(1, self.cfg)["removed"], 1)
        self.assertTrue(keep.exists())


class CliParsingTests(unittest.TestCase):
    def test_success_and_reported_usage(self):
        answer, usage = bridge.parse_cli(json.dumps([{"type": "system"}, success_event()]))
        self.assertEqual(answer, "answer")
        self.assertEqual(usage["input_tokens"], 20)
        self.assertIsNone(usage["credits"])

    def test_invalid_failed_and_tool_using_responses_rejected(self):
        values = [
            "not json",
            "[]",
            json.dumps({**success_event(), "is_error": True}),
            json.dumps([{"type": "tool_use"}, success_event()]),
            json.dumps([{"type": "assistant", "message": {"content": [{"type": "tool_call"}]}}, success_event()]),
        ]
        for raw in values:
            with self.subTest(raw=raw), self.assertRaises(bridge.BridgeError):
                bridge.parse_cli(raw)

    def test_json_lines_and_bom_are_accepted_without_relaxing_event_checks(self):
        raw = "\ufeff" + json.dumps({"type": "system"}) + "\n" + json.dumps(success_event()) + "\n"
        answer, usage = bridge.parse_cli(raw)
        self.assertEqual(answer, "answer")
        self.assertEqual(usage["input_tokens"], 20)
        with self.assertRaises(bridge.BridgeError):
            bridge.parse_cli(json.dumps({"type": "tool_use"}) + "\n" + json.dumps(success_event()))

    def test_invalid_json_reports_shape_not_raw_worker_output(self):
        raw = "Private source text must not appear in an error."
        with self.assertRaises(bridge.BridgeError) as caught:
            bridge.parse_cli(raw)
        self.assertEqual(caught.exception.details["code"], "invalid_worker_json")
        self.assertEqual(caught.exception.details["stdout_shape"], "plain_text")
        self.assertNotIn(raw, str(caught.exception) + str(caught.exception.details))
        mixed = json.dumps(success_event()) + "\nprivate diagnostic line"
        with self.assertRaises(bridge.BridgeError) as mixed_error:
            bridge.parse_cli(mixed)
        self.assertEqual(mixed_error.exception.details["code"], "invalid_worker_json")
        self.assertNotIn("private diagnostic line", str(mixed_error.exception.details))

    def test_invalid_json_with_permission_stderr_is_classified(self):
        with self.assertRaises(bridge.BridgeError) as caught:
            bridge.parse_cli("not JSON", "EPERM: private path withheld")
        self.assertEqual(caught.exception.details["code"], "access_denied")

    def test_child_environment_drops_api_keys(self):
        cfg = {**bridge.DEFAULT_CONFIG, "node_path": sys.executable}
        with patch.object(bridge, "installation", return_value=(sys.executable, Path("C:/fake/cli"))), patch.dict(
            os.environ, {"OPENAI_API_KEY": "secret", "PATH": "safe", "USERPROFILE": str(Path.home())}, clear=True
        ):
            _, environment = bridge.build_command(cfg)
        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertEqual(environment["PATH"], "safe")


if __name__ == "__main__":
    unittest.main()
