---
name: workbuddy-delegate
description: Delegate bounded low-risk text extraction, summarization, classification, translation, rewriting, and code drafts to the user's installed WorkBuddy while Codex verifies the result. Use for independent text batches that would otherwise consume substantial context; never use for consequential decisions, credentials, external actions, or final unverified claims.
---

# WorkBuddy Delegate

Use the bundled MCP tools to reduce primary-task context use without transferring final judgment.

## Route a task

1. Keep the task in Codex when it is small, ambiguous, consequential, requires tool use, changes files, sends messages, makes medical/legal/financial claims, or determines final research evidence.
2. Consider delegation when the work is independent, text-only, low-risk, and either spans at least three files, roughly 4,000+ characters, or a repetitive batch.
3. Call `workbuddy_plan` if eligibility is unclear. It makes no model request.
4. Call `workbuddy_status` before the first real delegation in a task. If WorkBuddy, Node, Python, an allowed root, quota, or model is unavailable, continue in Codex and report the precise blocker.
5. Pass only explicit relative UTF-8 file paths beneath a user-approved root, or short text supplied by the user. Never pass credentials, hidden configuration, entire drives, or unrelated files.
6. Use `delegate_to_workbuddy` with `risk="low"`. Prefer `dry_run=true` when checking a new workspace or job envelope.
7. Treat every result as a draft. Verify its meaning against cited excerpts and the user's request. Use `workbuddy_read_result` only when the preview is truncated and the full draft is needed.

## Manage locally

Configuration changes are intentionally excluded from model tools. `workbuddy_status` returns `manager_command`, the exact local command for the installed plugin.

Preserve every argument in `manager_command`, including `--config` and `--state-dir`,
and append the management subcommand. A bare manage.py command may edit a different
configuration from the running MCP. After changes, call the native `workbuddy_status`
again and verify its config path, model, and allowed roots before file delegation.
For older servers without these arguments, explicitly use the returned config_path
and state_path as WORKBUDDY_DELEGATE_CONFIG and WORKBUDDY_DELEGATE_STATE_DIR for the
local management process. Never infer success from the manager's output alone.

Use the native MCP for delegation. If a shell fallback encounters Windows access
denied, request the host's normal scoped execution approval; do not disable the
sandbox, copy credentials, or broaden filesystem permissions. A missing allowed
root requires authorization for that exact project, not a whole drive. Do not
convert blocked file input into inline text to bypass the file allowlist.

Use the manager for:

- `doctor` or `status`: offline installation check.
- `config init`, `config show`, and `config set KEY VALUE`: non-secret settings.
- `roots add PATH`, `roots list`, and `roots remove PATH`: explicit file-access allowlist.
- `usage --days 7`: local invocation counts.
- `cache prune`: delete expired local result artifacts.
- `self-test`: offline routing test.

Do not ask for or copy WorkBuddy API keys. This plugin reuses the user's existing WorkBuddy login and configuration.

## Evidence boundary

- A structurally valid result is not proof that the answer is correct.
- WorkBuddy-reported credits are not USD and may be unavailable.
- Do not promise lower cost, equal quality, or complete historical auditing.
- The WorkBuddy bundled CLI is an internal compatibility surface and may change after a WorkBuddy update.
