# Privacy

WorkBuddy Delegate runs locally and does not operate its own remote service.

## Data flow

When a real delegation is approved, the plugin sends the instruction and explicitly selected text to the model/provider configured by the user's existing WorkBuddy installation. That provider's terms and data controls apply. The plugin does not copy, display, or store WorkBuddy API keys.

The plugin stores locally:

- non-secret settings and allowed roots;
- a SQLite invocation ledger containing date, request fingerprint, and status;
- result artifacts containing the worker answer, short exact quotations, uncertainties, and provider-reported usage fields.

Default retention is 30 days for result artifacts. Run `manage.py cache prune` to remove expired artifacts. The invocation ledger is not a billing record and credits are not interpreted as currency.

## File access

File delegation is disabled until a user adds an allowed root. Each request must name at most 24 explicit relative UTF-8 files. Parent traversal, resolved paths outside the workspace, binary files, common credential names, and private configuration directories are rejected.

## No telemetry

This project adds no telemetry, analytics, advertising identifier, or developer-operated data collection.
