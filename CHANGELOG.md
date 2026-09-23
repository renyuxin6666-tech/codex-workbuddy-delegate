# Changelog

## 0.1.1 - 2026-09-23

- Legacy Codex MCP launch now resolves the same `PLUGIN_DATA` config/state paths as the portable plugin, or requires explicit paired paths; it no longer silently falls back to an unrelated legacy directory.
- Legacy MCP passes the path variables through to the launcher for scoped headless runs.
- WorkBuddy JSON and JSONL event output are both accepted when every event is valid; malformed output reports only shape/size metadata or a sanitized worker error, never raw output.
- Added regression tests for path parity, fail-closed startup, JSONL, and non-leaking diagnostics.

## 0.1.0 - 2026-09-17

- Initial Agent Plugins v1 and Codex compatibility package.
- Dependency-free local MCP transport.
- WorkBuddy discovery, bounded text delegation, exact-quote checks, cache, and local usage ledger.
- User-managed allowed roots, minimal child environment, duplicate-call guard, and artifact retention.
- Local manager for doctor, config, roots, usage, pruning, dry runs, and offline self-test.
