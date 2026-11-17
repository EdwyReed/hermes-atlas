# Optional mask and censor

Explicit user intent only. Never add segmentation/censoring as an automatic
filter, policy gate or generation step. All inference, weights, caches and jobs
belong to Engine; profiles contain no model runtime. Check `mask.health` or
`censor.health` and current capabilities without installing or starting anything.

## Mask files

`atlas_mask {action:"setup",image_path:"/absolute/image.png"}` chunk-uploads
through `media.upload.*`, verifies ingress, then calls `mask.setup`. Retain the
returned cache ID. Segment with `action:"segment"`, `cache_id`, explicit
`output_dir`, points/box, optional `multimask`, `annotate_prompts` and a stable
`request_id`. Point coordinates and XYXY boxes use original stored-raster pixels,
not display-scaled/EXIF-transposed coordinates. Labels are 1 foreground, 0
background. Multimask normally returns three candidates; overlays alone are not
masks. Inspect every requested candidate and select explicitly.

The adapter creates a unique child directory, retrieves masks, overlays,
float32 1×256×256 logits and original manifest, and verifies each artifact’s
size/SHA-256. White mask is foreground; an application may use it as alpha only
when requested. No pixel transformation occurs in this transport plugin.

Refinement uses `prior:{manifest_path:"/absolute/output/manifest.json",candidate:0}`.
A separate `.atlas-receipt.json` maps to the exact previous Engine job without
rewriting its manifest. Old manifests with `engine_job_id` remain supported.
Pre-cutover manifests without a job ID upload the exact selected candidate’s
logits plus manifest, not PNGs or a guessed best candidate. Preserve originals.
Cache IDs expire on idle/eviction/restart; rerun setup for an expired cache, not
an unapproved new segmentation. `release`/`reset` remain explicit operations.

## Censor files and queued work

`atlas_censor` (`anime_mosaic` transitional alias) accepts `action:"process"`,
existing `input_dir`, separate `output_dir`, stable `request_id`, and optional
`mode:"mosaic"|"black"|"blur"`, strength, confidence, padding, include_nipple,
include_anus, include_testicles and preview. It enumerates only immediate
PNG/JPEG/WebP files, 1–200 per batch. Originals stay unchanged. Existing outputs
require explicit overwrite. Preview selects the first N sorted inputs, not a
quality sample.

Censor admission can return queued/running. The unified adapter reads the exact
returned job back and reports `{ok:true,accepted:true,pending:true,job_id,state}`;
it does not classify acceptance as failure or claim output delivery. Use:

```json
{"action":"get","job_id":"RETURNED_ID","output_dir":"/absolute/censored","wait_seconds":30}
```

This only polls `censor.get` and downloads on terminal success; it never submits
new work. Use `atlas_mask action:get` or `atlas_files action:collect,kind:mask`
for the equivalent mask path. Poll time is bounded; repeat get with the same ID
when still pending. A transport failure after known admission retains job ID so
recovery also uses get. Unknown submit ACK is separate: retain exact request and
payload; never blindly replay or assign a new ID. Capacity/busy rejection is not
queued admission. Failed/interrupted jobs are not silently restarted.

Completion retrieval keeps remote manifests byte-exact and stores a separate
local receipt. Collection is resumable when existing files match exact hashes;
differing files require overwrite. It rejects traversal names, foreign-job
artifacts, corrupt/empty/oversized chunks and checksum mismatches. Partial files
are not advertised as complete delivery; recover by collecting the same job.

## Detection is not coverage

Inspect manifest counts and actual pixels. Separate processed files, detections,
covered regions and unchanged no-detection copies. A successful job or model-load
smoke check does not establish detection quality. Report missed coverage instead
of accepting an unchanged copy automatically. If manual editing is requested as
a fallback, label it separately from automatic detection acceptance.
