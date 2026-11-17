# Generation and workflows

## Resolve, plan, submit

`atlas_engine` takes exactly `{operation, arguments}`. All business rules, jobs,
models and native connections live in Engine. Read current `capabilities` and the
exact schema via `atlas_files {action:"schema", operation:"generation.plan"}`.
For multi-connection operations preserve both `connection_id` and
`backend_generation` from live capabilities; do not invent a default binding.

Resolve exact checkpoints and LoRAs using `catalog.list` and `catalog.resolve`.
LoRAs are `{model, weight}`, not name strings or `{name:...}`. Preserve literal
names, keys and weights, then inspect the resolved plan components.

```json
{"operation":"generation.plan","arguments":{"mode":"txt2img","model":"EXACT_CATALOG_MODEL","loras":[],"prompt":"requested prompt","negative_prompt":"text, watermark","width":768,"height":1024,"steps":8,"cfg":1.0,"seed":42,"scheduler":"euler"}}
```

Submit the same approved fields through `generation.submit`, adding a stable
`request_id` saved before submission. Use a new ID for changed payloads. Preserve
the exact payload for uncertain-ACK reconciliation; never retry automatically.
Anima turbo recipes often use `anima_turboV11`, euler, CFG 1, 8–10 steps. A
project’s explicit recipe wins. At CFG <=1, stored negative text may not be
connected to the denoiser: verify the plan/PNG graph, put essential ownership and
anatomy in the positive prompt, and never claim conditioning from metadata alone.

Read `generation.get {job_id}` and `generation.wait {job_id, timeout_seconds:30}`.
The latter returns `{job,timed_out}`; timeout is not failure. Keep Engine job IDs
separate from native queue IDs. `generation.retry` is an explicit terminal retry,
not timeout recovery. `generation.cancel` targets the exact existing job.
`jobs.events` provides bounded progress. Follow pagination for complete history.

Use `batch.submit` for 2–4 runs with `request_id` and `runs` plus the generation
fields. Monitor `batch.get` and each child’s final state, outputs and seeds. A
queue total or one completed native item is not batch completion.

## Input and mode limits

Native input upload is separate from media upload:
`atlas_files {action:"upload", path:"/absolute/source.png",
request_id:"stable-source-v1", namespace:"native", role:"image"}` performs
chunked `upload.begin/chunk/finalize`, returns upload ID, size and SHA-256, and
never silently imports. Inspect `upload.get` and the live `upload.import` schema
before an authorized import to obtain a real remote `image_name`. Local paths
are never remote IDs. Unknown import ACK requires reconciliation, not reupload.

Native image ingress accepts static PNG/JPEG within 32 MiB/24 MP; masks are L-mode
PNG, white=edit, black=preserve. Preserve public mask bytes; Engine normalizes
native polarity. Inpaint needs matching source/mask/output dimensions and family,
remote `image_name`, `mask_name`, and `strength`. A full-white mask represents
whole-canvas img2img. Studio composite-refine recipes normally use strength <=.35
and cap .4; do not impose this project convention on unrelated outpainting.

Check actual enabled modes: currently only txt2img is accepted for generation.
A planner accepting `inpaint` or `upscale` does not enable submission. Current
canvas schema is 64–1536, multiples of 8, with possible stricter family limits.
Preserve an incompatible 1792×576 stitch as an unsupported requirement; do not
silently shrink or reframe it.

Pixel upscale is image-space processing, not diffusion refinement. Its schema
uses `mode:"upscale"`, `image_name`, exact upscaler `model`, `scale` and
`upscale_engine:"spandrel"|"esrgan"`; omit prompts/LoRAs. Preserve originals and
record any RGB PNG conversion needed to remove alpha, ICC, EXIF rotation or
animation. The older low-VRAM tile-256 recipe is not representable when the
planner fixes tile 512. Never invent a `tile`, `argv`, `out`, or CLI escape hatch.

## Saved recipes

Read `workflows.list`, `workflows.get`, `workflows.schema` for the exact key and
input/output contract. `workflows.run` is bounded native saved-workflow execution,
not arbitrary graph execution. Preserve explicit version semantics, exposed
fields, image/dimension mappings and selected return node. Observed preflight
revision/hash is not proof of the executed revision. A named upscale-plus-SD1.5
metadata-refine recipe must retain the refinement checkpoint, denoise, input
mapping and final return node; pixel upscale is not a substitute.

## Delivery, boards and review

Use `artifact.list` or `artifact.fetch {job_id,image_name}` for exact linked
outputs. `atlas_files {action:"download",job_id:"ID",image_name:"name.png",
path:"/absolute/project/outputs/name.png"}` obtains the descriptor and assembles
bounded chunks, checks size/SHA-256 and reads saved bytes back. `collect` with
`kind:"generation"`, `job_id`, `output_dir` handles all linked artifacts and
polls for at most `wait_seconds:30`; repeat collection on the same ID to resume.
An empty artifact list is not delivery. Batch parents may require collection of
each child. Do not scrape native storage or unrelated images for missing outputs.

Inspect actual images for requested quality checks. `review.prepare/record`
retain a supplied judgment and artifact hash; they do not perform vision.
`image.metadata` and PNG `invokeai_metadata`/`invokeai_graph` can recover exact
parameters. Actual connected LoRA/model nodes establish participation, not prompt
mentions. Preserve original files and project ledgers.

Boards use exact IDs from `boards.list/get/images`, not display names.
`boards.create`, `boards.images.update`, `boards.update/delete` are authorized
admin mutations with stable IDs and revision readbacks. Removing membership uses
`action:"remove"`, not a guessed source-board move. Virtual `board_id:"none"`
is uncategorized inventory. Keep `include_images:false` for empty-board deletion.
Admin mutations may return journal jobs; follow `admin.get` then read the exact
board/model target before success. `ack_unknown` is a reconciliation state.
