---
name: atlas
description: "Use for Atlas images, workflows, models, dream and masks."
---

# Atlas

Use the shared Atlas Engine for generation, saved workflows, model/catalog and
corpus operations, enrichment/dreaming, artifact delivery, masks and censoring.
Artistic booru prompt craft belongs in the separate `danbooru` skill.

## Start here

1. Use the active profile’s `atlas_engine` with
   `{ "operation": "capabilities", "arguments": {} }`.
   Read exact live operation schemas with `atlas_files` action `schema`, operation
   `generation.plan` (or the operation you need). Omitting operation lists names.
   `GET /v1/schema` is authoritative; field presence does not mean enabled execution.
2. Read the matching reference before execution:
   - [Generation and workflows](references/generation-workflows.md): planning,
     exact recipes, stable request IDs, batches, uploads, delivery, boards/review.
   - [Models and corpus](references/models-corpus.md): exact assets, triggers,
     onboarding, author/community galleries, editable records and provenance.
   - [Enrichment and dream](references/enrich-dream.md): numerical proposals,
     evidence, identity drift, feedback and exact-job recovery.
   - [Mask and censor](references/mask-censor.md): local files, every candidate,
     selected-prior refinement, asynchronous censor and verified delivery.
   - [Profile guidance](references/profile-guidance.md): preserved private recipes
     and project requirements from earlier profile skills.
3. Preserve requested models, prompts, files, weights, dimensions and request IDs.
   Plan first; submit only the requested work. Follow the returned Engine job ID.
   Read terminal state, retrieve original artifacts, verify size/SHA-256, then
   inspect requested visual results before calling them usable.

## Execution boundaries

- One plugin, one skill (`atlas:atlas`), shared code; separate profile settings
  and existing credentials. No token copying, permission expansion, service
  restarts, model/dependency downloads, profile reconfiguration or silent fallback
  to native InvokeAI, old scripts, databases or Qdrant.
- `atlas_engine` preserves the full Engine operation surface and envelopes;
  `atlas_files` performs chunked file transfer without base64 in model context.
  `atlas_mask` and `atlas_censor` are file conveniences; `anime_mosaic` is a
  temporary alias in this same plugin, not another backend.
- Missing tools/credentials, `FORBIDDEN`, disabled modes and downtime are different
  failures. Report the exact gap. A guidance-only profile keeps its existing
  read-only proxy; this package does not grant a new connection.
- Never auto-replay an unknown acknowledgment. Preserve exact intent/request ID,
  inspect existing receipts, and reconcile before any explicit retry. A pending
  job is accepted, not failed. Poll the same job; do not submit another one.
- Mask/censor are optional explicit actions, never automatic post-filters.
  Engine review stores host judgments; it does not inspect pixels.
- Current known deployment limits: only txt2img is enabled for generation;
  saved workflows are bounded typed recipes, not arbitrary graphs. Re-read live
  capabilities. CPU censor execution does not establish detection coverage;
  numerical dream/enrich output does not establish character fidelity.

## Verification

A capability response proves connectivity, not inference. For delivery check the
exact job, every requested artifact, saved byte hashes and visual result. Keep
originals unchanged. Use `MEDIA:/absolute/path.png` where the surface supports it.
Report pending work, partial source coverage and unsupported requirements plainly.
