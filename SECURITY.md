# Security policy

## Supported version

Security fixes target the latest tagged release. v0.1.0 is community/experimental and Windows-first.

## Design controls

- Empty file-access allowlist by default.
- Explicit relative paths only; path resolution must remain under both workspace and allowed root.
- Common secret/config filenames and directories blocked.
- Worker tools, MCP servers, hooks, and memory disabled for delegated calls.
- Minimal child environment allowlist; inherited API-key variables are not forwarded.
- Daily request cap, input cap, timeout, cache, result retention, and in-flight duplicate guard.
- Local management commands own configuration changes; the model-facing MCP does not mutate config.
- Exact source quotations are checked mechanically; semantic correctness still requires Codex review.

## Reporting

Please use GitHub Security Advisories for vulnerabilities. Do not include credentials, private source text, or raw WorkBuddy configuration in a report.

## Known boundary

The adapter launches an internal CLI bundled with WorkBuddy. That interface may change, and the WorkBuddy/provider security and privacy policies remain independent of this project.
