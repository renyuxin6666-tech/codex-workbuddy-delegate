"""Verify the installed MCP server with one explicit, non-sensitive fixture."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser()
entry = parser.add_mutually_exclusive_group(required=True)
entry.add_argument('--server')
entry.add_argument('--launcher')
parser.add_argument('--config', required=True)
parser.add_argument('--state-dir', required=True)
parser.add_argument('--live', action='store_true')
parser.add_argument('--instruction', default='Return exactly Willow: 42 as the answer. Cite the source sentence verbatim.')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
environment = dict(os.environ, WORKBUDDY_DELEGATE_CONFIG=args.config,
                   WORKBUDDY_DELEGATE_STATE_DIR=args.state_dir)
job = {'instruction': args.instruction,
       'workspace': str(root), 'files': ['tests/fixtures/dispatch-smoke.txt'],
       'kind': 'extract', 'risk': 'low', 'dry_run': not args.live}
request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
           'params': {'name': 'delegate_to_workbuddy', 'arguments': job}}
command = (["cmd.exe", "/d", "/s", "/c", "call", str(Path(args.launcher).resolve())]
           if args.launcher else [sys.executable, '-X', 'utf8', args.server])
process = subprocess.run(command,
                         input=json.dumps(request) + '\n', encoding='utf-8',
                         capture_output=True, env=environment, timeout=160)
response = json.loads(process.stdout)['result']
value = response['structuredContent']
print(json.dumps(value, ensure_ascii=False, indent=2))
if response.get('isError'):
    raise SystemExit(1)
if args.live:
    record = json.loads(Path(value['artifact']).read_text(encoding='utf-8'))
    assert record['result']['answer'].strip() == 'Willow: 42', 'Semantic fixture mismatch'
else:
    assert value['request_sent'] is False
