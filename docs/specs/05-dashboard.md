# 05: Dashboard and Access Control

## Goal and ownership

Requires 04 and shared contract 00; fake-data rendering can start after 01. Budget: 75 minutes.
Own `streamlit_app.py`, `dashboard.py`, `access.py`, Streamlit theme and UI/access tests.

## User experience

The first screen is an operational dashboard, not a landing page. Use native Streamlit controls,
a light restrained theme, compact headings and readable status colors. Show synthetic provenance
and last-read time; show message count, current processed, pending and error/invalid counts.
Provide category/priority charts, searchable/filterable results and full original-text/action detail.
Counters and charts describe the filtered population. Hide stale insights from current analytics.
Make empty, no-match, missing configuration, denied access and API outage states explicit.
Render untrusted text as plain text; do not inject HTML or silently replace live data with fixtures.

Cache only read-only sheet snapshots for 60 seconds, keyed by configured spreadsheet/tab.
Public refresh respects the cache; authorized refresh and completed processing invalidate it.
Pipeline reads are uncached. Do not share non-thread-safe clients or cache paid/write side effects.

## Access and jobs

Public visitors may browse but not process. Store a random password of at least 24 characters in
secrets. Use constant-time comparison and server-side session authentication; remove the typed
password after verification and provide logout. Missing password/configuration or disabled
processing denies jobs. Recheck authorization inside every processing entry point.

Authorized commands: Process pending, Retry errors, Reprocess selected. Enforce at most five
messages in the service. Fixed sheet/model configuration is not public input. Processing happens
only on the explicit button event, never on import, page load, filtering or generic rerun.

Use a global `threading.Lock` shared through `st.cache_resource`, nonblocking acquisition and
`finally` release. Add a shared ten-second job-start cooldown. A per-session flag alone is insufficient.
This does not coordinate machines or provide production identity, RBAC or a durable billing cap.

## Acceptance

AppTest verifies anonymous browsing, wrong passwords and missing settings make zero paid/write
calls; authorized clicks execute once and reruns do not repeat; lock contention reports busy and
errors release the lock; stale-result counts are correct. Verify desktop and mobile layout in a
real browser. Optional CSV export must neutralize spreadsheet formulas; omit it if time is tight.