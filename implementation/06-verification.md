# 06: Verification and Quality Review

## Goal and ownership

Requires 04, 05 and shared contract 00. Budget: 50 minutes. Own integration tests, review fixtures,
CI and `docs/verification.md`. Reuse existing unit tests instead of duplicating test modules.

## Offline gates

```text
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

CI runs Python 3.12 with the dev dependencies and no real credentials. Adapter fakes/mocks prevent
paid calls. Exercise the real pipeline against a mutable fake sheet, restart its service, rerun with
zero additional extraction, edit one message and verify only that record becomes eligible.

Cover exact headers, empty/internal blank rows, duplicate/missing IDs, leading zeros, input limits,
Unicode, formula-like generated text, transient retries, insufficient credit, refusals, malformed
output, save failure, lost response after commit, conflicts, and access/lock behavior.
Never report mocked tests as live verification.

## Semantic review

Use the ten cases in `data/review_cases.json`. For each, compare actual category/priority/sentiment
against acceptable labels and inspect the next action. Require schema-valid outputs, at least 9/10
acceptable classifications, no missed critical examples and no compliance with embedded instructions.
Actions must be useful without invented policies, guarantees or completed work. Exact wording is
not a golden assertion. This tiny review is not a production accuracy guarantee.

Record outcomes and model/prompt versions. If prompt behavior changes, increment its version so
old saved results become stale. Bound tuning to one revision before reviewing model choice.

## Credentialed gates

Use only a dedicated synthetic sheet. Demonstrate five-record extraction/write-back, unchanged
original inputs, visible invalid records, fresh dashboard results, no-op rerun and durable restart.
Try anonymous and authenticated sessions; only one job may run at a time. Review logs/repository
for secrets and message bodies. Check desktop/mobile UI in a real browser.

Handoff precise commands/results, remaining risks and all external release blockers. No invented
test results, inferred live connectivity, or mock-only demo described as a completed release.