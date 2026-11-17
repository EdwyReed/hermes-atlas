# hermes-atlas

A standalone Hermes Agent plugin for Atlas Engine. One plugin (`atlas`), one
bundled skill (`atlas:atlas`), and five tools. This repository is the client;
it does not ship Atlas Engine or require its source checkout.

| Tool | Purpose |
| --- | --- |
| `atlas_engine` | Literal operation/arguments passthrough to `/v1/ops/<operation>` |
| `atlas_files` | Live schemas, chunked upload, exact-job artifact download and collection |
| `atlas_mask` | Explicit segmentation setup, candidates, selected-prior refinement and collection |
| `atlas_censor` | Explicit file-batch censoring and exact-job collection |
| `anime_mosaic` | Transitional alias of `atlas_censor` in the same plugin |

Models, inference, native connections, databases, workflows and durable jobs
stay in Engine. No old adapter paths or Engine Python imports are used. File
payloads travel in bounded HTTP chunks, not through the model context.

## Install

See [INSTALL.md](INSTALL.md) for pinned installation, profile-local settings,
legacy migration and rollback. Installation is separate from live gateway
activation. Do not restart an occupied gateway to finish a package check.

Requirements: a current Hermes runtime with `ctx.register_skill`, namespaced
skill lookup, plugin settings and `agent.file_safety`; Python 3.11+;
`jsonschema>=4.18,<5` (declared in the plugin manifest). The migration helper also
uses the runtime's PyYAML and `hermes config set --force`. An existing authorized
Atlas HTTP endpoint and this profile's explicit credential binding are needed
for tools; without them the skill is available but tool availability is false.

## Use

Load `atlas:atlas` and the relevant bundled reference. Start with:

```json
{"operation":"capabilities","arguments":{}}
```

Read the exact live schema with `atlas_files`:

```json
{"action":"schema","operation":"generation.plan"}
```

`atlas_engine` preserves Engine arguments and result envelopes. Schema presence
is not permission or proof that a mode is enabled. `allowed_operations`, when
configured, restricts operation calls; Engine remains the authorization boundary.
Schema discovery uses a separate authenticated `GET /v1/schema`.

For an admitted job, collect the same ID instead of submitting again:

```json
{"action":"collect","kind":"generation","job_id":"RETURNED_JOB_ID","output_dir":"/absolute/project/outputs/run","wait_seconds":30}
```

A pending response means accepted work, not delivered files. Collection checks
job identity, artifact names, size and SHA-256, then verifies saved bytes.
Original manifests stay unchanged; `.atlas-receipt.json` is a separate local
receipt. Recollection accepts existing identical files; different bytes require
explicit overwrite. A completed job with no artifacts is not image delivery.

## Safety and limits

- No automatic write retries. An unknown acknowledgment retains request identity
  where available; reconcile existing intent before an explicit retry.
- Credentials are read only from this profile's explicit `token_file` or named
  `token_env`. No cross-profile credential discovery, copying or fallback.
- HTTPS, or loopback HTTP only; redirects and environment proxies are disabled.
  No credential-bearing URL fields. Tokens are redacted from returned JSON.
- Absolute local paths pass Hermes read/write safety checks. Downloads reject
  unsafe names, symlinks, foreign-job descriptors and checksum mismatches.
- Upload budgets: media 64 MiB, native 32 MiB; artifact budget 256 MiB per file;
  JSON responses 8 MiB; HTTP timeout 1–60 seconds. Job polling is at most 30
  seconds per collection, plus bounded transport calls. This is not a whole-call
  wall-clock deadline. Transfers currently assemble each file in memory.
- Optional mask/censor actions are never implicit post-filters. Successful
  execution does not establish detection quality or visual acceptance.
- Legacy guidance is preserved privately under the same profile during migration.
  It is never bundled into this repository. Artistic `danbooru` remains separate.

## Verification

From this directory, using Python with the current Hermes runtime importable:

```bash
python -m unittest discover -s tests -v
hermes plugins doctor "$PWD" --ci
hermes plugins validate "$PWD"
```

The suite has 14 loopback/mock tests. It exercises transport, file integrity,
queued recovery, no replay, credential isolation, migration apply/rollback,
interrupted migration, and fresh-process native discovery of all five tools,
one skill and all its references in temporary homes. No live profile, model
inference, native write or service restart is required.

The validator currently warns about two imports from `agent.file_safety`.
These are the host's file-boundary checks; this dependency is intentional and
must be rechecked on Hermes upgrades, not removed to silence the warning.
A fixture pass is not live installation or inference acceptance.

## Source and distribution

The client and bundled technical guidance are maintained here independently of
Engine. No model weights, third-party implementation source, profile settings,
credentials, personal history or runtime receipts are included. This repository
does not grant a license to redistribute third-party engines or models.
