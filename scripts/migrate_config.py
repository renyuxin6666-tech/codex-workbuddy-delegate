"""Explicitly migrate existing non-secret settings to an uninitialized MCP config."""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "workbuddy-delegate" / "scripts"))
import workbuddy_bridge as bridge

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", required=True)
parser.add_argument("--target", required=True)
args = parser.parse_args()
source = Path(args.source).resolve(strict=True)
target = Path(args.target).resolve()
if target.exists():
    raise SystemExit("Target already exists; refusing to overwrite its settings.")
os.environ["WORKBUDDY_DELEGATE_CONFIG"] = str(source)
cfg = bridge.load_config()
os.environ["WORKBUDDY_DELEGATE_CONFIG"] = str(target)
bridge.save_config({key: cfg[key] for key in bridge.DEFAULT_CONFIG})
print("Migrated existing non-secret settings. Verify with native workbuddy_status.")
