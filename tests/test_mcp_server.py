from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "workbuddy-delegate" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import mcp_server


class HandlerTests(unittest.TestCase):
    def test_initialize_ping_and_notifications(self):
        initialized = mcp_server.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}
        )
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "workbuddy-delegate")
        self.assertEqual(mcp_server.handle({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"], {})
        self.assertIsNone(mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_tools_list_has_unique_names_and_schemas(self):
        result = mcp_server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})["result"]
        names = [tool["name"] for tool in result["tools"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("delegate_to_workbuddy", names)
        delegation = next(tool for tool in result["tools"] if tool["name"] == "delegate_to_workbuddy")
        self.assertEqual(delegation["inputSchema"]["properties"]["risk"]["enum"], ["low"])

    def test_tool_success_and_business_error_shapes(self):
        with patch.object(mcp_server, "status", return_value={"installed": True}):
            response = mcp_server.handle(
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "workbuddy_status", "arguments": {}}}
            )
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(response["result"]["structuredContent"], {"installed": True})
        response = mcp_server.handle(
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "unknown", "arguments": {}}}
        )
        self.assertTrue(response["result"]["isError"])

    def test_invalid_and_unknown_requests(self):
        self.assertEqual(mcp_server.handle({"jsonrpc": "2.0", "id": 6})["error"]["code"], -32600)
        self.assertEqual(mcp_server.handle({"jsonrpc": "2.0", "id": 7, "method": "missing"})["error"]["code"], -32601)
        invalid = mcp_server.handle(
            {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "workbuddy_status", "arguments": []}}
        )
        self.assertEqual(invalid["error"]["code"], -32602)


class ProcessTransportTests(unittest.TestCase):
    def test_json_lines_transport_and_eof(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = os.environ.copy()
            environment["WORKBUDDY_DELEGATE_CONFIG"] = str(Path(temporary) / "config.json")
            environment["WORKBUDDY_DELEGATE_STATE_DIR"] = str(Path(temporary) / "state")
            messages = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "ping"},
            ]
            process = subprocess.run(
                [sys.executable, "-X", "utf8", str(SCRIPTS / "mcp_server.py")],
                input="\n".join(json.dumps(message) for message in messages) + "\n",
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=10,
            )
        self.assertEqual(process.returncode, 0, process.stderr)
        responses = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual([response["id"] for response in responses], [1, 2, 3])
        self.assertEqual(process.stderr, "")

    def test_parse_error_and_array_rejection(self):
        outgoing = mcp_server._error(None, -32700, "Parse error")
        self.assertEqual(outgoing["error"]["code"], -32700)
        # serve() handles a batch array as an invalid request instead of processing it.
        self.assertEqual(mcp_server.handle({"id": 1})["error"]["code"], -32600)

    @unittest.skipUnless(os.name == "nt", "Legacy launcher is a Windows batch file")
    def test_legacy_launcher_uses_plugin_data_not_legacy_home(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = os.environ.copy()
            for name in ("WORKBUDDY_DELEGATE_CONFIG", "WORKBUDDY_DELEGATE_STATE_DIR", "CLAUDE_PLUGIN_DATA"):
                environment.pop(name, None)
            environment["PLUGIN_DATA"] = temporary
            request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "workbuddy_status", "arguments": {}}}
            process = subprocess.run(
                ["cmd.exe", "/d", "/s", "/c", "call", str(SCRIPTS / "launch_mcp.cmd")],
                input=json.dumps(request) + "\n", text=True, encoding="utf-8",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=SCRIPTS.parent, env=environment, timeout=15,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            status = json.loads(process.stdout)["result"]["structuredContent"]
            self.assertEqual(Path(status["config_path"]), Path(temporary) / "config.json")
            self.assertEqual(Path(status["state_path"]), Path(temporary) / "runtime")

    @unittest.skipUnless(os.name == "nt", "Legacy launcher is a Windows batch file")
    def test_legacy_launcher_explicit_paths_override_plugin_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            environment = os.environ.copy()
            environment["PLUGIN_DATA"] = str(base / "other")
            environment["WORKBUDDY_DELEGATE_CONFIG"] = str(base / "experiment" / "config.json")
            environment["WORKBUDDY_DELEGATE_STATE_DIR"] = str(base / "experiment" / "runtime")
            request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "workbuddy_status", "arguments": {}}}
            process = subprocess.run(
                ["cmd.exe", "/d", "/s", "/c", "call", str(SCRIPTS / "launch_mcp.cmd")],
                input=json.dumps(request) + "\n", text=True, encoding="utf-8",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=SCRIPTS.parent, env=environment, timeout=15,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            status = json.loads(process.stdout)["result"]["structuredContent"]
            self.assertEqual(Path(status["config_path"]), base / "experiment" / "config.json")
            self.assertEqual(Path(status["state_path"]), base / "experiment" / "runtime")

    @unittest.skipUnless(os.name == "nt", "Legacy launcher is a Windows batch file")
    def test_legacy_launcher_fails_closed_without_paths(self):
        environment = os.environ.copy()
        for name in ("WORKBUDDY_DELEGATE_CONFIG", "WORKBUDDY_DELEGATE_STATE_DIR",
                     "PLUGIN_DATA", "CLAUDE_PLUGIN_DATA"):
            environment.pop(name, None)
        process = subprocess.run(
            ["cmd.exe", "/d", "/s", "/c", "call", str(SCRIPTS / "launch_mcp.cmd")],
            input="", text=True, encoding="utf-8", stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=SCRIPTS.parent, env=environment, timeout=10,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("config path is missing", process.stderr)

    @unittest.skipUnless(os.name == "nt", "Legacy launcher is a Windows batch file")
    def test_legacy_launcher_rejects_half_of_explicit_pair(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = os.environ.copy()
            environment["PLUGIN_DATA"] = str(Path(temporary) / "plugin")
            environment["WORKBUDDY_DELEGATE_CONFIG"] = str(Path(temporary) / "custom.json")
            environment.pop("WORKBUDDY_DELEGATE_STATE_DIR", None)
            process = subprocess.run(
                ["cmd.exe", "/d", "/s", "/c", "call", str(SCRIPTS / "launch_mcp.cmd")],
                input="", text=True, encoding="utf-8", stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, cwd=SCRIPTS.parent, env=environment, timeout=10,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("both explicit config and state paths", process.stderr)


if __name__ == "__main__":
    unittest.main()
