# Implementation Spec Index

## Goal

Read synthetic customer support messages from Google Sheets, extract four validated insights
with an LLM, write results to the same records, and expose a local/public Streamlit dashboard.
Public viewing is allowed; live processing requires a private operator password.

## Small-context workflow

Give an implementation agent only `00-contract.md`, its active sheet, and the relevant code/tests.
Do not require the original chat or the entire repository. Implement only the active slice.
Run the narrow tests immediately after changes. Record changed files, interface changes, commands
and results, blockers, and the next sheet in a handoff of at most 200 words.
Update the shared contract before changing an interface consumed by other sheets.

| Sheet | Dependency | Budget | Purpose |
| --- | --- | --- | --- |
| [00 Contract](00-contract.md) | None | Shared | Stable schema and operating constraints |
| [01 Foundation](01-foundation.md) | 00 | 45 min | Package, configuration and models |
| [02 Sheets](02-sheets.md) | 01 | 55 min | Read/write adapter and reconciliation |
| [03 LLM](03-llm.md) | 01 | 45 min | Structured extraction and failures |
| [04 Pipeline](04-pipeline.md) | 02, 03 | 75 min | Selection, processing and durable results |
| [05 Dashboard](05-dashboard.md) | 04 | 75 min | UI and protected processing |
| [06 Verification](06-verification.md) | 04, 05 | 50 min | Tests, quality review and live checks |
| [07 Release](07-release.md) | 06 | 60 min | Hosted executable URL and handoff |

Allow 75 minutes of contingency: eight hours total. Start account setup during sheet 01.
Sheets 02 and 03 can be implemented in parallel with separate file ownership.
Deployment preparation can start early; release acceptance cannot bypass verification.

## Current handoff

Core modules, dashboard, synthetic seed data, tests and deployment configuration are implemented.
See [verification status](../docs/verification.md) for what has actually been checked.
No live credentials or hosted application URL have been supplied. Do not equate mocked tests with
live integration verification. Optional CLI, CSV export and automated scheduling are excluded.