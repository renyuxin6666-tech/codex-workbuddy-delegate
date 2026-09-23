"""Regression: MCP plugin data and an ordinary terminal must target the same config."""
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
import workbuddy_bridge as bridge


class ManagerPathsTests(unittest.TestCase):
    def test_status_command_survives_missing_plugin_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            config = base / "plugin data" / "config.json"
            state = base / "plugin data" / "runtime"
            workspace = base / "project"
            workspace.mkdir()
            with patch.dict(os.environ, {
                "WORKBUDDY_DELEGATE_CONFIG": str(config),
                "WORKBUDDY_DELEGATE_STATE_DIR": str(state),
            }), patch.object(bridge, "installation", return_value=(sys.executable, base)):
                command = bridge.status()["manager_command"]
            env = dict(os.environ)
            env.pop("WORKBUDDY_DELEGATE_CONFIG", None)
            env.pop("WORKBUDDY_DELEGATE_STATE_DIR", None)
            env["WORKBUDDY_DELEGATE_HOME"] = str(base / "unrelated-home")
            result = subprocess.run(command + ["roots", "add", str(workspace)],
                                    env=env, cwd=base, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(config.read_text())["allowed_roots"], [str(workspace.resolve())])
            self.assertFalse((base / "unrelated-home" / "config.json").exists())
            (workspace / "note.txt").write_text("A verified fixture.")
            with patch.dict(os.environ, {"WORKBUDDY_DELEGATE_CONFIG": str(config),
                                         "WORKBUDDY_DELEGATE_STATE_DIR": str(state)}), \
                    patch.object(bridge, "installation", return_value=(sys.executable, base)):
                output = bridge.delegate("Extract the fixture", str(workspace),
                                         kind="extract", files=["note.txt"], dry_run=True)
            self.assertFalse(output["request_sent"])
            usage = subprocess.run(command + ["usage"], env=env, cwd=base,
                                   capture_output=True, text=True)
            self.assertEqual(usage.returncode, 0, usage.stderr)
            self.assertTrue((state / "usage.sqlite3").exists())

    def test_status_reports_denied_installation_without_losing_config_path(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {
            "WORKBUDDY_DELEGATE_STATE_DIR": temporary,
        }), patch.object(bridge, "installation", side_effect=PermissionError("denied")):
            result = bridge.status(dict(bridge.DEFAULT_CONFIG))
        self.assertFalse(result["installed"])
        self.assertIn("--config", result["manager_command"])


if __name__ == "__main__":
    unittest.main()
