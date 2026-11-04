# Three-Minute Demo

Prerequisites: configured synthetic Google Sheet, working model access, hosted app, private
operator password supplied to the evaluator separately. Never distribute API/service-account keys.

1. Open the hosted dashboard anonymously. Inspect saved categories, priorities and sentiments.
2. Select a pending record and inspect the original message. Show that the public view has no
   processing controls. Optionally open the synthetic Google Sheet with view-only access.
3. Unlock processing using the private password. Choose Pending and a small batch size, then Process.
4. Show the confirmed saved count and full suggested action. Verify the four outputs in the same
   sheet row while the ID and original message remain unchanged.
5. After the cooldown, repeat Pending when no eligible rows remain: no paid reprocessing occurs.
6. Inspect MSG-030: its blank text is invalid without an LLM call. To demonstrate recovery, the owner
   may supply a message while no job is running; its changed fingerprint makes it eligible.
7. Reprocess selected IDs when all pending examples have been used. Refresh/restart to show that
   persisted results are read from Sheets, not retained only in browser memory.

Before sharing, process about 20 of the 30 examples and leave pending rows available. Do not add
a destructive reset control. Use separate sheets for local development and the hosted demo.