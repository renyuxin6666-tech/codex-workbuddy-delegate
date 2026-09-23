# 2026-09-23 experiment preflight: stopped before scored A/B runs

**Evidence state:** development diagnostic / `inconclusive`. The 12 paired cases in
[`PROTOCOL.md`](PROTOCOL.md) have **not** run. There are no quality scores and no
measured saving ratio. This report is a tool-chain checkpoint, not evidence that
the plugin saves or wastes Token on the planned task population.

## Frozen observations

- Plugin source commit: `db7b1e0`; installed plugin version:
  `0.1.0+codex.20260923050437`; WorkBuddy model shown by status:
  `deepseek-v3-2-volc`.
- Desktop Codex model `gpt-6-sol` was rejected by the installed CLI when using
  ChatGPT login. `gpt-5.6-sol` was also rejected because the CLI was too old.
  Neither failure yielded a completed-turn usage record. The installed CLI was
  `0.155.0-alpha.16`.
- The same CLI completed a one-word `gpt-5.5`, medium-effort usage smoke:
  24,512 Codex input tokens (2,432 cached input), 28 output tokens. This proves
  a per-run meter exists for that model; it does not establish A/B readiness.
- A CLI-to-WorkBuddy fixture preflight in read-only mode reached
  `workbuddy_status` but the subsequent `delegate_to_workbuddy` MCP call was
  cancelled (`user cancelled MCP tool call`). Completed-turn usage: 170,742
  Codex input tokens (141,568 cached input), 1,370 output tokens. No worker
  answer was obtained.
- A second, distinct fixture preflight used the documented on-request policy
  with automatic approval review and the workspace-write sandbox. The delegate
  call reached the bridge but failed validation with `WorkBuddy returned
  invalid JSON; inspect login and client health.` Completed-turn usage:
  277,753 Codex input tokens (242,048 cached input), 2,126 output tokens. No
  worker answer or attributable WorkBuddy usage was obtained. It was not
  retried.
- These **three completed Codex smokes used 476,531 input + output tokens in
  total**. This is diagnostic overhead, not an A/B efficiency result; the
  rejected-model attempts lack reliable usage and are not included. Cached
  input is already included in input tokens and was not added again.

## Configuration split and remaining uncertainty

The desktop/native plugin status reported its configuration and state under a
plugin-specific data directory. The older CLI's compatibility MCP launcher
instead used the legacy `%LOCALAPPDATA%/WorkBuddyDelegate` configuration and
state directory. Both showed the intended WorkBuddy model and allowed project
root, but their daily call ledgers differed. This is a confirmed **path split**
and violates the protocol's identical-configuration precondition. It is **not
yet proven** to be the cause of the invalid JSON; the worker's raw output was
not retained or exposed because it may contain source text or credentials.

The plugin's own dry-run for the public fixture passed local file, installation,
and state checks with `request_sent=false`. A dry-run does not prove login or
network health. An earlier native desktop fixture completed in the plugin data
state, but cannot substitute for the failed CLI invocation or a paired case.

## No-request routing controls

| Control | Observation | Evidence boundary |
|---|---|---|
| NC01 high risk | `workbuddy_plan` returned `route=codex` | Plan sends no model request. |
| NC02 credential-shaped path | A synthetic, credential-free file named `credentials_dummy.txt` was rejected before file reading | Error does not explicitly include `request_sent`; code path rejects in `read_sources`, before `invoke`. |
| NC03 unapproved directory | Dry-run returned `workspace_not_allowed`, `request_sent=false` | No file was read. |
| NC04 external action | Marked `risk=high`; `workbuddy_plan` returned `route=codex` | This tests caller risk labeling, not natural-language detection by the plugin. |

No real credential path or unapproved file content was sent to WorkBuddy.

## Stop decision and resumption gate

Formal A/B runs remain at **0/12 pairs**. Do not compute `pilot_go` or
`pilot_no_go`; current status is `inconclusive`. Before the first scored run:

1. Make the desktop and headless CLI use one *experiment-specific* config and
   state path; retain the exact project-root allowlist, fixed WorkBuddy model,
   and `cache_hours=0`. Verify both native statuses agree.
2. Diagnose the worker's invalid-JSON response without logging raw source or
   credentials. Run one bounded, non-scored fixture preflight with a completed
   delegate result and attributable usage. Do not switch paid models or retry a
   failed worker call automatically.
3. Freeze 12 independent document packs and gold atoms before A/B; obtain the
   independent human gold check and blind quality ratings required by the
   protocol. Keep inputs and gold isolated.
4. Only then start the randomized 6 AB / 6 BA sequence with the same Codex
   model and effort in both arms. Record every failure and missing usage.

The synthetic routing-control file and raw local run records are intentionally
excluded from Git. The public report contains only de-identified metadata.
