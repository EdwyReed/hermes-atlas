# Numerical enrichment and dream

Read current schemas for `enrich`, `dream.submit/get/cancel`, `evidence` and
`feedback.*`. These are bounded mathematical proposals without a generative LLM.
They do not render images or inspect pixels. The plugin never reimplements their
graph, ranking, vocabulary or database.

Supply exact source references, prompt/tags, `locked_tags`, characters/fandoms,
explicit bindings, model, seed, budget, count and trajectories only as accepted by
the live schema. Preserve unresolved inputs and source attribution. Keep CPU
proposal work independent from GPU rendering; do not enqueue proposals silently.

Persist the exact dream payload and stable request ID before submission. Read
`dream.get {job_id}` on the returned ID. Pending/uncertain/submitting is not an
invitation to launch another dream. Unknown ACK needs exact-intent reconciliation.
A deliberate changed input is a new intent with a new ID; retain the old receipt.
Do not infer rejection from absence on a first page of jobs.

## Quality checks

Inspect evidence for the requested identity and ancestry of proposed tags. Common
bridges such as `1girl` or `solo` can lead into unrelated characters, fandoms and
meta tags when an exact identity has no incident observations. `locked_tags`
preserves literal tokens, not semantic identity or requested scene ownership.
A seeded numerical result is not verified character guidance. Explicitness and
other numeric controls are inputs to the algorithm, not proof that it respected
the creative brief.

Compare requested identity, source-supported attributes and proposed additions;
report missing evidence and drift plainly. Do not write invented graph edges,
silently promote uncertain source prose to observations, or render a drifted
proposal as though it were approved. Preserve original tags and source text
separately from derived indexes. Use `feedback.record/list` for attributed
keep/reject/revise notes; the current annotation-only policy does not change
ranking automatically. Apply approved edits explicitly to subsequent input.

Completion means a terminal exact-job result, usable evidence and an honest
quality judgment for the requested purpose. Numeric execution alone proves only
that the algorithm ran. `atlas_files collect kind:dream` can read terminal state,
but dreams may have no image artifacts: do not represent an empty file set as
image delivery.
