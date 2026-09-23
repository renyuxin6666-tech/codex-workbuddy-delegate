import json
import sqlite3
from unittest.mock import patch
from test_bridge import IsolatedTest, bridge
import mcp_server


class PreflightTests(IsolatedTest):
    def test_denied_root_has_exact_repair_command(self):
        with self.assertRaises(bridge.BridgeError) as caught:
            bridge.delegate('Extract', str(self.base), files=['note.txt'], dry_run=True)
        details = bridge.error_payload(caught.exception)
        self.assertEqual(details['code'], 'workspace_not_allowed')
        self.assertFalse(details['request_sent'])
        self.assertEqual(details['repair_command'][-3:], ['roots', 'add', str(self.base)])
        self.assertIn(str(self.base / 'config.json'), details['repair_command'])

    def test_dry_run_checks_storage_without_model_or_quota(self):
        with patch.object(bridge, 'installation'), patch.object(bridge, 'invoke') as invoke:
            result = bridge.delegate('Rewrite', str(self.base), kind='rewrite', text='hello', dry_run=True)
        self.assertEqual(result['local_checks'], 'passed')
        self.assertEqual(result['live_connectivity'], 'not_checked')
        invoke.assert_not_called()
        self.assertEqual(bridge.usage()['runs'], {})

    def test_denied_storage_blocks_before_model(self):
        with patch.object(bridge, 'installation'), patch.object(bridge.tempfile, 'TemporaryFile', side_effect=PermissionError()), \
                patch.object(bridge, 'invoke') as invoke, self.assertRaises(bridge.BridgeError) as caught:
            bridge.delegate('Rewrite', str(self.base), kind='rewrite', text='hello')
        self.assertEqual(caught.exception.details['code'], 'state_unavailable')
        invoke.assert_not_called()

    def test_worker_errors_do_not_leak_raw_output(self):
        for raw, code in [('401 secret-token', 'login_required'), ('429 secret-token', 'quota_or_rate_limit'),
                          ('EACCES secret-token', 'access_denied'), ('ECONNRESET secret-token', 'network_error')]:
            value = bridge.error_payload(bridge.cli_failure(raw))
            self.assertEqual(value['code'], code)
            self.assertNotIn('secret-token', json.dumps(value))

    def test_status_preserves_paths_when_ledger_denied(self):
        with patch.object(bridge, 'installation'), patch.object(bridge, 'usage', side_effect=sqlite3.OperationalError('locked')):
            # Return the expected tuple rather than relying on a mock's iteration.
            with patch.object(bridge, 'installation', return_value=('node', self.base)):
                result = bridge.status()
        self.assertIsNone(result['calls_today'])
        self.assertEqual(result['state_error']['code'], 'ledger_unavailable')
        self.assertIn('--state-dir', result['manager_command'])

    def test_sqlite_error_is_mcp_tool_error(self):
        with patch.object(mcp_server, 'usage', side_effect=sqlite3.OperationalError('locked')):
            result = mcp_server.handle({'jsonrpc':'2.0','id':1,'method':'tools/call',
                                        'params':{'name':'workbuddy_usage','arguments':{}}})
        self.assertTrue(result['result']['isError'])
        self.assertEqual(result['result']['structuredContent']['code'], 'ledger_unavailable')
