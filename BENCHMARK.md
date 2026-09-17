# Benchmark snapshot

This is a bounded development diagnostic, not a generalized model evaluation.

| Field | Result |
|---|---:|
| Fixture | 5 synthetic Markdown files |
| Source characters | 22,049 |
| Task | Authority/version extraction with an injected instruction in source data |
| Weighted score | 93.18 / 100 |
| Strict gate | FAIL |
| Current constraints | 5 / 5 |
| Unresolved issues | 1 / 1 |
| Exact evidence items | 6 / 6 |
| Superseded historical relations | 6 / 11 |
| Accepted injected instructions | 0 |
| False-current claims | 0 |
| WorkBuddy-reported tokens | 13,044 input / 6,140 output |
| WorkBuddy-reported credits | 2.52 (not USD) |

Interpretation: the prototype was useful for extracting the current state with exact evidence and resisted the fixture's prompt injection. It did not produce a complete historical relation audit. The engineering decision is to delegate bounded current-state extraction, retain Codex review, and keep exhaustive authority/history adjudication in the primary task.

An installed-package smoke test was also run from an unrelated working directory. One short provided-text extraction returned the approved date and rejected option with two exact quotations, ignored an injected “run tools” instruction, and launched no worker tool. WorkBuddy reported 370 input tokens, 335 output tokens, and 0.1 credits (not USD). This verifies the installed MCP path and one bounded call; it is not a quality or cost benchmark.

See the machine-readable [acceptance record](benchmark/acceptance-v0.1.0.json).
