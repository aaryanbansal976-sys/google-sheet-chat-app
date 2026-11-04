# 07: Deploy and Deliver

## Goal and ownership

Requires 06 and shared contract 00; prepare accounts during 01. Budget: 60 minutes.
Own README, evaluator walkthrough and Streamlit Community Cloud configuration.
Deliver a real reachable HTTPS executable URL in addition to the local utility.

## Prerequisites

Owner supplies GitHub/Community Cloud access, Google service-account credentials, private synthetic
spreadsheet shared as Editor with that account, an LLM API key/billing, and private operator password.
Resolve organization restrictions through an administrator. Do not publish credentials or request
them through the chat. The sheet must never be public-editable.

## Deployment

Publish the repository with owner authorization. Select `streamlit_app.py` as the Community Cloud
entry point and explicitly choose Python 3.12. Deployment requirements install the local package.
Put API key/model, fixed spreadsheet/tab, password, enabled flag and service-account table in Cloud
Secrets, using the same structure as the ignored local secrets file. Verify model access and
supported request options with one synthetic request. Enable billing alerts/available limits;
these and per-run limits are not necessarily hard spending caps.

Preprocess about 20 synthetic records; leave pending examples for assessors. Privately share the
processing password, not API credentials. Selected reprocessing allows repeated demonstrations
without resetting the sheet. Do not run local/cloud writers against the same sheet concurrently.

## Release acceptance

In an incognito browser, open the actual hosted URL, inspect populated results, confirm anonymous
processing is denied, unlock processing, run a record and inspect the four persisted insights in
both UI and Sheet. Check normal rerun, refresh, mobile layout and process restart. Record URL/date.
Hosting can sleep and has resource constraints; state those limitations. Screenshots/videos are
supplements, not substitutes for the executable link.

README starts with the real live URL once verified and includes local commands, exact headers,
taxonomy, secrets/sharing setup, tests, recovery, versions and concurrency limits. A three-minute
walkthrough covers raw message -> authenticated processing -> persisted result -> no-op rerun.

Definition of done: working public URL, accessible live processing for authorized assessors,
verified real Sheet writes, reproducible local startup, passing offline gates, no leaked credentials,
visible errors and demonstrated restart behavior. If credentials/accounts block release, mark it
blocked; never substitute localhost, an invented URL or mock results for the hosted deliverable.