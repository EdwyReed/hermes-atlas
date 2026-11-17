# Models, discovery and corpus

## Exact lookup and evidence

Use `catalog.list/resolve/get` for the live inventory. Use `search` with `mode`
(not `search_mode`); explicitly retry literal lookup if semantic/hybrid is
unavailable. `evidence {kind,key}` uses exact tags/resources/characters/fandoms/
references/research/feedback; `knowledge.get {entity_id}` resolves returned IDs.
Historical knowledge, editable records, native catalog and canonical corpus are
different sources. Search recall is not a complete inventory. Respect returned
`has_more`, `next_after`/`after` and source totals; enumerate programmatically
before claiming all models or galleries were checked.

Match model registration key, literal filename, name, base/family and exact hash.
A `live_inventory_only` placeholder is not trigger documentation. Compare full
catalog LoRA snapshots, paginated `knowledge.search kind:resource` and `loras.list`
before declaring coverage. Missing search hits do not erase project evidence.
Preserve source/profile attribution; shared knowledge is not personal biography.

## Triggers and creator guidance

Keep exact-version trained words, version descriptions and model-level creator
notes attributed separately. An empty trainedWords array does not mean no trigger
exists. Search source-language weight advice too (`权重`, `權重`, `重み`,
`ウェイト`, `強度`, `强度`). Distinguish activation phrases, optional helper tags,
alternative prompt groups and full scene examples. Never import separators such
as `---other prompt---` or merge alternatives into mandatory triggers.

Use literal hashes with their declared algorithm. BLAKE3 exact lookup can identify
renamed files; verify the returned model-file hash and exact version applicability.
A changed hash under one native key is a provenance discrepancy, not permission to
repair it. Compare trigger values as sets while preserving source arrays. Do not
infer human edits from nonempty fields or disagreement with trainedWords; use
before snapshots/ledgers. Verify prompt insertion/escaping for the model family
rather than assuming A1111 escapes.

For sites configured to use `civitai.red`, preserve that domain for site/API calls;
never fall back to `civitai.com`. Issued image/model CDN URLs are distinct allowed
byte sources, not permission to send source credentials to storage. Preserve
signed URLs literally without logging them. Source redirects/HTTP200 do not prove
completed file transfer, hash verification or registration. Use an honest Atlas
User-Agent, bounded credential-free CDN redirects and representation-bound cache
validators. Do not export provider keys/browser cookies from their existing host.

## Installation and onboarding

Read schemas before authorized `models.install`, `models.lora.install`,
`models.checkpoint.install`, `models.acquire.*`, `models.onboard` or refresh.
`models.scan {source_id}` discovers a configured source, not an arbitrary local
path or installation. Do not start model downloads merely for discovery.
Track journal jobs (`admin.get`, `models.job`, onboarding get) and read native
catalog and knowledge targets back. A synchronous installer can remain
`submitting`; recover from exact existing jobs, registry/hash and task-owned file
progress before starting another worker. `models.acquire.page`, not an invented
`models.acquire.get`, enumerates acquisition history.

Registered-file gallery onboarding is separate from native installation. Supply
exact registered key, literal native path and native registry hash algorithm/value.
Follow `models.onboard.get`; resume the same frozen partial intent after a
transport fix instead of reinstalling. `succeeded` may still mean `partial:true`.
Record missing source data as unknown, never fabricated prompt/trigger metadata.
Verify imported image bytes using `corpus.files.read {sha256,offset,size}` in chunks
<=32768. Keep canonical history, historical knowledge and derived numeric indexes
separate; do not write direct SQLite/Qdrant or invent automatic indexing parity.

## Gallery completeness

Where selected by the project, collect 30 unique community examples by default
PLUS the entire exact-version author carousel without a numerical cap. Author
examples do not consume the community quota. Deduplicate storage while retaining
both source memberships and independent unique counts. Source IDs with identical
bytes retain distinct attribution. Ordering is provenance, not a coverage gate
unless explicitly required. Preserve prompts, negatives, all resource weights,
parameters, tags/relations and resumable source intent without thematic selection.

Reconcile raw exact-version author posts and each post’s paginated image IDs,
`imageCount`, known carousel assets and source aliases. The version `images`
serializer/cache branch may be capped and is a witness, not exhaustive coverage.
Use exact-version creator posts, not all creator uploads or mere resource mentions.
For permitted Civitai metadata retrieval inspect actual deployed schemas; REST
image requests need `withMeta=true`. Explicit all-level browsing mask 31 includes
PG/PG13/R/X/XXX; boolean `nsfw=true` is not equivalent. Preserve source access
restrictions, exact continuation cursors and version association separately from
resources recorded in image generation. Distinguish authentication/domain/recency
issues from genuine gallery exhaustion.

## Editable records and acceptance

For approved documentation use `loras.create/get/update/history`; updates carry
`expected_revision` and the full merged body. Read exact records back. These are
metadata edits, not installs or guaranteed embeddings/historical-card rewrites.
For editorial image decisions use `generation.records.*` with exact artifact/job/
image IDs, prompt, LoRAs, seed, source feedback and project status; preserve original
artifacts/accepted ledgers. `feedback.record` is job-level annotation, not a
per-image acceptance index. No automatic ranking or Qdrant write is implied.
