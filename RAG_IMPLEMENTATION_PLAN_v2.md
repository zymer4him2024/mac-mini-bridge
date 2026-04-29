# RAG + Multi-Channel Companion — Implementation Plan v2

*Gemma 4 E4B edition. Supersedes `RAG_IMPLEMENTATION_PLAN.md` (v1, 2026-04-28) for execution; v1 is kept as historical baseline. This version standardizes on the Gemma E-series model family already running on the Mac Mini, engineers around its weaker tool-calling, and folds in critique surfaced after v1 was written.*

---

## 0. Why v2 (delta from v1)

| Area | v1 | v2 |
|---|---|---|
| Embedding model | `nomic-embed-text` (768d) | **`embeddinggemma`** (768d, RAG-tuned). `nomic-embed-text` retained as Phase D fallback. |
| Generation model | `llama3.1:8b` | **`gemma4:e4b`** (canonical, per `.env`). |
| Tool-routing model | Same as generation | **`llama3.1:8b`** (separate, hybrid orchestration). Engineered around Gemma E-series weak function-calling. |
| Summary tuning | None scheduled | **Phase B.5** — A/B summary prompt; this is the retrieval ceiling, not embeddings. |
| Multimodal | Not mentioned | **Phase B.6** — embed image-attachment captions via `gemma4:e4b` vision. |
| Eval set size | 20 questions | 60 questions across 4 categories. |
| `query_leads` filter | Hand-wavy | Strict Pydantic schema with allow-listed fields + operators, OR cut from v1 if scope risks Phase C. |
| Vector store framing | Firestore Vector Search committed; abstraction "for swap someday" | Firestore Vector Search default, **but FAISS-on-disk + nightly GCS snapshot surfaced as a real alternative** with a decision gate at end of Phase A. |
| Re-indexing | Implicit (`messageId` dedup) | Explicit `embeddingVersion` field; selective re-embed when prompt/model bumps. |
| Privacy framing | "Embeddings derived from summaries, not raw bodies" listed as inversion mitigation | Removed (it's a downgrade, not a mitigation). Per-user isolation is the actual mitigation. |
| Hardware budget | Implicit | Explicit RAM ceiling pinned per model + warm-cache assumption. |

Total: 9 new files (same as v1), ~14 files modified — but the file content differs in non-trivial places. Estimate stretches from v1's 10–14 days to **12–17 days** because of the new B.5 + B.6 phases and the hybrid orchestration.

---

## 1. Decisions Locked In

| Decision | Choice | Why it matters |
|---|---|---|
| Embedding model | **`embeddinggemma`** (768-dim) | RAG-tuned, leaderboard-strong at this size, drop-in for the Firestore vector schema. One-line swap to `nomic-embed-text` if Phase D recall is <70%. |
| Generation / synthesis / summarization | **`gemma4:e4b`** | Already the runtime per `.env`. Multimodal-capable (text + image + audio input). MatFormer / per-layer-embedding architecture means low active-parameter count at inference. |
| Tool-routing | **`llama3.1:8b`** (Q4, already pulled) | Gemma E-series has weaker function-calling than Llama. We isolate the tool-choice step — a single, low-token call — to Llama, then hand off to Gemma for synthesis. |
| Vector store (default) | **Firestore Vector Search** | Native to existing stack; per-user isolation maps to `users/{uid}/embeddings`. |
| Vector store (alternative, decision gate) | **FAISS on local disk + nightly GCS snapshot** | At single-digit-user scale: sub-10ms retrieval, zero monthly cost, zero vendor lock-in. Decision gate at end of Phase A: choose Firestore if multi-host writers are imminent, FAISS if not. |
| Delivery surfaces | **Telegram (v1) + Slack (Phase F)** | Telegram for power users / dogfood. Slack added because that's where US SMB customers actually live. Portal at `apps/email2ppt-portal` stays untouched in this plan. |

---

## 2. What You Already Have (Do Not Rebuild)

```
[OK] Multi-tenant pipeline (per-user Gmail OAuth, Firestore-stored)
[OK] watcher.py     — 5-min poll, summarize, PDF, lead upsert, Telegram alert
[OK] digest.py      — 7am daily roll-up   (already on gemma4:e4b)
[OK] ppt.py         — on-demand deck from Gmail query
[OK] bridge.py      — Telegram bot ↔ Ollama with Gmail tools
[OK] firestore_leads.py / firestore_users.py / firestore_telegram.py
[OK] KMS envelope encryption, log redaction, audit, GDPR cleanup, retention sweeps
[OK] Pydantic schemas at Telegram boundary
[OK] launchd plists for all jobs
[OK] CI: ruff + bandit + mypy strict + gitleaks + pre-commit
[OK] llama3.1:8b already pulled — reused as the tool-routing model in v2
```

---

## 3. What's Being Added

```
+ Ollama: pull embeddinggemma (768d, ~600MB)
+ Firestore: new collection users/{uid}/embeddings/{id} with vector field
  + new field: embeddingVersion (lets us re-embed on prompt/model bumps)
  + new chunkType value: 'attachment' (Phase B.6)
+ embeddings.py            — Ollama embedding wrapper, retries, redaction
+ firestore_embeddings.py  — upsert / search / per-user delete
+ orchestrator.py          — NEW. route_intent (Llama) + synthesize (Gemma)
+ Hooks (1 line each)      — watcher.py, digest.py, ppt.py
+ bot_core.py              — channel-agnostic bot logic (extracted from bridge.py),
                             routes through orchestrator.py
+ bridge.py                — refactored to thin Telegram I/O wrapper
+ slack_bridge.py          — Slack Bolt webhook + message-format adapter
+ slack_install.py         — OAuth install flow per workspace
+ firestore_slack.py       — workspace tokens (KMS-wrapped)
+ slack_app_manifest.yaml  — bot scopes, slash commands, event subscriptions
+ Cloudflare Tunnel        — secure public HTTPS for Slack Events API webhook
+ backfill_embeddings.py   — one-time index of existing leads
+ vision_caption.py        — NEW (Phase B.6). Captions image attachments via gemma4:e4b
+ Updated GDPR + retention — wipe embeddings + Slack tokens on user delete
+ docs/runbook-rag-index.md, docs/runbook-slack-channel.md
+ Eval set: 60 Q&A pairs   — recall + answer-quality regression baseline
                             (Direct lookup / Cross-corpus / Mixed / Multimodal)
```

---

## 4. Data-Flow Map (Hybrid Orchestration)

```
   Gmail email
      │
      ▼
  watcher.py ── summarize_email() (gemma4:e4b)
      │                │
      │                ▼
      │      ┌─────────────────────┐
      │      │ NEW: index_for_rag()│
      │      │   ↓                  │
      │      │ embeddings.py        │
      │      │   ↓ (embeddinggemma) │
      │      │ firestore_embeddings │
      │      │   ↓                  │
      │      │ users/{uid}/         │
      │      │   embeddings/{id}    │
      │      │   - text (summary)   │
      │      │   - embedding (768d) │
      │      │   - embeddingVersion │
      │      │   - chunkType        │
      │      │   - leadId, msgId    │
      │      └─────────────────────┘
      ▼
  build_pdf() ─→ disk + Telegram (unchanged)
  upsert_lead() ─→ Firestore (unchanged)

  Image attachments (Phase B.6):
      │
      ▼
  vision_caption.py ── gemma4:e4b (vision input)
      │
      ▼
  caption text ─→ embeddings.py ─→ chunkType: 'attachment'


   Telegram message  (or Slack DM, post-Phase F)
      │
      ▼
  channel adapter (bridge.py / slack_bridge.py)
      │
      ▼
  bot_core.handle_message(uid, text)
      │
      ▼
  orchestrator.route_intent(text)
      │   model: llama3.1:8b (Q4) — strong tool-calling
      │   returns: { tool: 'rag_search' | 'query_leads' | 'search_emails' | 'read_email' | 'create_draft', args: {...} }
      ▼
  execute_tool(tool, args, uid)
      │   • rag_search       → vector retrieval over user's corpus
      │   • query_leads      → Pydantic-validated structured Firestore query
      │   • search_emails    → live Gmail (unchanged)
      │   • read_email       → live Gmail (unchanged)
      │   • create_draft     → Gmail compose (unchanged)
      ▼
  context bundle (top-k chunks + metadata)
      │
      ▼
  orchestrator.synthesize(question, context)
      │   model: gemma4:e4b — fluent generation, citation rendering
      ▼
  Reply with citations:
   "Per lead Acme (3 emails, last 2026-04-25): they want…"
```

The two-model split is the load-bearing architectural choice in v2. `llama3.1:8b` only sees the user message + tool catalog and returns a structured choice; it never sees retrieved content. `gemma4:e4b` only sees the question + retrieved chunks and returns prose; it never has to decide anything. Each model does what it's best at.

---

## 5. New Data Model

**Collection:** `users/{uid}/embeddings/{embedding_id}`

| Field | Type | Notes |
|---|---|---|
| `embedding` | `Vector(768)` | `embeddinggemma` output. Firestore vector field. |
| `embeddingVersion` | string | e.g. `"embeddinggemma-v1"`. Bump when model or summary prompt changes; backfill script re-embeds only mismatched docs. |
| `text` | string | The text that was embedded — typically the LLM-generated summary, OR an attachment caption (`chunkType=attachment`). |
| `chunkType` | enum | `summary` \| `subject` \| `digest` \| `attachment` |
| `leadId` | string | Joins to `users/{uid}/leads/{leadId}` |
| `messageId` | string | Gmail msg ID. Dedup key. |
| `attachmentId` | string \| null | Set only when `chunkType=attachment`. Gmail attachment ID for retrieval. |
| `senderEmail` | string | Denormalized for filter clauses |
| `senderName` | string | |
| `subject` | string | |
| `urgency` | string | Mirrors lead doc |
| `createdAt` | timestamp | `SERVER_TIMESTAMP` |
| `userId` | string | Denormalized for security rule simplicity |

**Index (Firestore CLI):**
```sh
gcloud firestore indexes composite create \
  --collection-group=embeddings \
  --query-scope=COLLECTION_GROUP \
  --field-config field-path=embedding,vector-config='{"dimension":768,"flat":{}}'
```

**Security rule (additive to firestore.rules):**
```
match /users/{uid}/embeddings/{id} {
  allow read: if request.auth.uid == uid;
  allow write: if false; // server-only via admin SDK
}
```

---

## 6. Phase Plan

### Phase A — Foundation (1–2 days)

- `ollama pull embeddinggemma` on Mac Mini.
- Confirm `gemma4:e4b` is healthy (it should be — `.env` already targets it; `digest.py` already uses it).
- Create Firestore vector index (one-time gcloud command).
- Build `embeddings.py` (~80 lines).
- Build `firestore_embeddings.py` (~120 lines, includes `embeddingVersion` round-trip).
- Update `firestore.rules` + rules tests.
- Unit tests for both modules.

**Decision gate at end of Phase A:** Stick with Firestore Vector Search, OR pivot to FAISS-on-disk + nightly GCS snapshot. Decide based on:
- Multi-host writer requirement? (Cloud Run tenants per Phase C of the security plan) → **Firestore**.
- Single Mac Mini for the foreseeable horizon? → **FAISS** (lower latency, zero monthly cost, zero preview-API risk).

The abstraction layer in `firestore_embeddings.py` keeps this swappable; the rename to `vector_store.py` is trivial.

**Done when:** `python -c "from embeddings import embed_text; print(embed_text('hello').shape)"` returns 768-dim, and a roundtrip write/query against the chosen vector store returns the seeded doc.

---

### Phase A.5 — Tool-calling smoke test (half day) — NEW in v2

The hybrid orchestration is *opinionated about Gemma's tool-calling weakness*. Before we lock it in, validate empirically.

- Build a 10-prompt eval covering the 5 tools (`rag_search`, `query_leads`, `search_emails`, `read_email`, `create_draft`) with 2 prompts each — natural-language, paraphrased.
- Run twice: once against `gemma4:e4b` with tool catalog, once against `llama3.1:8b` with same prompts.
- Score by exact tool match.

**Decision gate:**
- Gemma scores ≥80% → **drop the Llama side**, use single-model `gemma4:e4b` for everything. Update §4 diagram.
- Gemma scores 60–80% → **hybrid as planned**.
- Gemma scores <60% → **slash-command-only routing**: drop auto-routing, expose `/ask`, `/search`, `/draft` as explicit commands. Simpler, single-model, but loses the natural-language fluency.

This phase is half a day and saves a week of debugging if assumptions are wrong.

---

### Phase B — Indexing (2–3 days)

- Add `index_for_rag(uid, email, summary, lead_id, embedding_version)` helper (best-effort, never raises — mirror `upsert_lead` pattern).
- Hook into `watcher.py` after `summarize_email()` (1 line).
- Hook into `digest.py` (1 line, dedup by `messageId`).
- Hook into `ppt.py` (1 line, dedup by `messageId`).
- Update `gdpr_local_cleanup.py` and `retention_sweep.py` to also delete embeddings.
- Build `backfill_embeddings.py` — walks all historical leads across every linked user. Embeds each lead's `lastSummaryResponse` + subject. Idempotent (skip if `messageId` + `embeddingVersion` matches), resumable (writes a checkpoint per user), rate-limited (configurable QPS to Ollama and the vector store), runs as an overnight launchd one-shot. Logs progress every 100 docs; emits a final per-user summary.
- Tests in `test_pipeline.py`.

**Done when:** A new email arrives → 30s later it's queryable via `firestore_embeddings.search_embeddings(uid, "test query")`.

---

### Phase B.5 — Summary-prompt tuning (1 day) — NEW in v2

The retrieval ceiling is set by `summarize_email()` quality, not by embeddings. v1 didn't budget time for this. Doing it cheaply:

- Pick 30 representative emails across senders / urgency levels.
- For each: run current summary prompt and 2 candidate revisions.
- Embed all 90 outputs. Build a held-out query set (15 questions) where we know which email is the right answer.
- Score recall@5 per prompt variant.
- Pick the winner; record in `docs/runbook-rag-index.md`.

If recall@5 differs by >5pp, it's worth deploying. If not, skip and revisit after eval data accumulates.

---

### Phase B.6 — Multimodal attachment embedding (1 day) — NEW in v2

Gemma 4 E4B accepts image input natively. Most email attachments today (screenshots, scanned invoices, charts, design mockups) are dropped on the floor by RAG; OCR-then-embed is fragile. Native vision captioning is cheaper and more robust.

- Build `vision_caption.py`. Single function: `caption_attachment(image_bytes, mime_type) -> str`. Calls `gemma4:e4b` with the image plus a prompt: *"Describe this attachment in 2–3 sentences. Focus on extractable facts: names, numbers, dates, action items."*
- In `watcher.py`: after `build_pdf()`, iterate over inline image attachments. For each, call `caption_attachment`, then `index_for_rag(..., chunkType='attachment', attachmentId=..., text=caption)`.
- Skip attachments >10MB or non-image types in v1.
- Cost guard: cap at 3 image attachments per email (the 4th, 5th, … get skipped with a log line). Real emails rarely exceed 3 useful images; this prevents a 50-image newsletter from torching the queue.
- GDPR delete already handles `users/{uid}/embeddings/**`; no extra wiring.

**Done when:** An email arrives with a JPEG of a scanned invoice → 60s later, "What's the invoice total from Acme?" returns the dollar amount via `rag_search`.

---

### Phase C — RAG retrieval in the bot (2–3 days)

- Build `orchestrator.py` with two functions:
  - `route_intent(text: str) -> {tool, args}` — calls `llama3.1:8b` (or whichever model Phase A.5 selected) with the tool catalog. Returns Pydantic-validated tool choice.
  - `synthesize(question: str, context: list[Chunk]) -> str` — calls `gemma4:e4b`. Renders citations like `[Acme · 2026-04-25]` inline.
- Build `bot_core.py` with `handle_message(uid, text)` that calls `route_intent`, dispatches to `execute_tool`, calls `synthesize`, returns reply. Channel-agnostic.
- Refactor `bridge.py` to a thin Telegram I/O wrapper around `bot_core.handle_message`. Behavior-preserving — must pass existing tests before merging.
- Add `rag_search(question, k=5)` to the tool catalog. Embeds the question via `embeddinggemma`, queries the vector store scoped to `request.auth.uid`, returns chunks + metadata.
- Add `query_leads(filter)` with **strict** Pydantic schema:
  ```python
  class LeadFilter(BaseModel):
      status: Literal['new', 'replied', 'archived'] | None = None
      urgency: Literal['high', 'medium', 'low'] | None = None
      sender_domain: str | None = Field(None, max_length=64, pattern=r'^[a-z0-9.-]+$')
      since_days: int | None = Field(None, ge=1, le=365)
      limit: int = Field(20, ge=1, le=100)
  ```
  If the schema feels brittle, **cut from v1** and let RAG handle aggregation via top-k synthesis. Decide at start of Phase C based on real query patterns observed during dogfood.
- Add Telegram command `/ask <question>` as an explicit RAG-first path (forces `rag_search` + `query_leads`, skips Gmail tool calls). Plain messages keep the auto-route — orchestrator picks via the routing model.
- Update Pydantic `schemas.py` with `RAGQuery` validator (length + char class).

**Done when:** "What did Acme say about pricing?" via Telegram returns a sourced answer pulled from indexed summaries (not Gmail re-fetch), with the routing decision logged so we can debug misroutes.

---

### Phase D — Eval & tuning (1–2 days)

- Build a **60-question** eval set across 4 categories:
  - Direct lookup (15) — "status of Acme deal?"
  - Cross-corpus aggregation (15) — "manufacturing leads with budget"
  - Mixed (15) — "most recent Acme email + summarize last 3 emails from them"
  - Multimodal (15) — "what's the total on the invoice from Beta Corp?" (Phase B.6)
- Sanity-check expected answers with the user (~30 min review).
- Run baseline (Gmail-tools only, no RAG) vs RAG-augmented vs RAG+multimodal.
- Track recall@5, citation accuracy, and routing accuracy in `test_eval.py`.
- Tune retrieval `k`, summary prompt (revisit Phase B.5 winner), routing prompt.

**Done when:** ≥80% of eval questions return a correct, cited answer; multimodal subset ≥70% (lower bar — vision-captioned chunks are noisier than summary chunks).

---

### Phase E — Docs (0.5 day)

- New: `docs/runbook-rag-index.md` (creating index, monitoring, embedding rotation, decision gate from Phase A on Firestore vs FAISS).
- Update `PRIVACY.md`: embeddings collection lifecycle, retention, deletion, multimodal captions of attachments. **Delete the v1 claim that embedding summaries reduces inversion-attack surface — it does not. Replace with: "Embeddings are scoped per-user via Firestore security rules; vector content is treated with the same retention and deletion guarantees as the source email summary."**
- Update `SECURITY.md`: vector store threat model, embedding-inversion notes, attachment-caption data flow.

---

### Phase F — Slack channel (3–4 days, after Phase C lands)

**Goal:** Add Slack as a second delivery channel sharing the same RAG/Ollama backend, so US SMB customers can use the bot inside the workspace they already live in.

**Architecture:**
- **Refactor first.** Phase C already extracted `bot_core.py` + `orchestrator.py` from `bridge.py`. Slack reuses these directly. No further refactor needed.
- **Reachability.** Telegram works via outbound long-poll (no public IP needed). Slack Events API is webhook-based — Slack POSTs to your endpoint, so the Mac Mini needs a public HTTPS URL. Use **Cloudflare Tunnel** (free, no port-forwarding, fits the local-first ethos). Endpoint: `https://email2ppt.<your-domain>/slack/events`.
- **Multi-tenancy.** Slack install is per *workspace*; map each workspace install to a `users/{uid}` document via the OAuth `installer.user_id` and an explicit "claim this install" step on the portal. Slack tokens stored at `users/{uid}/secrets/slack` with the existing KMS envelope wrap.

**Steps:**
1. Create Slack app via manifest (`slack_app_manifest.yaml`): bot scopes (`chat:write`, `app_mentions:read`, `im:history`, `im:write`, `commands`); slash command `/ask`; Events API subscriptions (`message.im`, `app_mention`).
2. Build `slack_install.py` — OAuth install flow, request signature verification, workspace ↔ user mapping.
3. Build `firestore_slack.py` — token CRUD with KMS wrapping (mirror `firestore_telegram.py`).
4. Build `slack_bridge.py` — Slack Bolt for Python (`slack-bolt` package), receives events, calls `bot_core.handle_message(uid, text)`, formats reply using Slack Block Kit (richer than Telegram plain text).
5. Stand up Cloudflare Tunnel — `cloudflared` daemon as a launchd job, `com.shawn.email-cloudflared.plist`.
6. Add Pydantic validator `SlackEvent` for incoming payloads.
7. Update `gdpr_local_cleanup.py` to also revoke + delete Slack tokens.
8. New runbook `docs/runbook-slack-channel.md` — install steps, tunnel setup, troubleshooting.

**Done when:** A second user installs the Slack app to their workspace via the portal's "Add to Slack" link, claims the install, then DMs `/ask what's the status of Acme deal?` to the bot in Slack and gets the same sourced answer they'd get from Telegram.

---

**Total estimate: 12–17 working days of focused build (Phases A–F).** Up from v1's 10–14 because of B.5 (1 day), B.6 (1 day), A.5 (0.5 day), and the more rigorous eval in D.

---

## 7. Smallest First Slice (1–2 hours, before any plumbing)

Three sanity checks. If any fail, replan before building.

```sh
# 1. Confirm embeddinggemma is available and produces 768-dim vectors
ollama pull embeddinggemma
ollama list | grep embeddinggemma
python -c "
import requests
r = requests.post('http://100.86.233.125:11434/api/embeddings',
                  json={'model':'embeddinggemma','prompt':'hello world'}).json()
print('dim =', len(r['embedding']))   # expect 768
"

# 2. Confirm gemma4:e4b vision works (Phase B.6 prerequisite)
python -c "
import base64, requests
img = base64.b64encode(open('test_invoice.jpg','rb').read()).decode()
r = requests.post('http://100.86.233.125:11434/api/generate',
                  json={'model':'gemma4:e4b',
                        'prompt':'Describe this invoice in 2 sentences.',
                        'images':[img]}).json()
print(r['response'])
"

# 3. Confirm vector-store write/query works (whichever store Phase A picks)
python smallest_first_slice.py     # script seeds 3 docs, queries
```

If those three return clean output, the rest is plumbing.

---

## 8. Files Changed

**New (Phases A–E, 5):**
- `embeddings.py`
- `firestore_embeddings.py` (or `vector_store.py` if FAISS path is chosen at Phase A gate)
- `orchestrator.py` — hybrid model orchestration (NEW in v2)
- `vision_caption.py` — multimodal attachment captioning (NEW in v2)
- `backfill_embeddings.py`
- `docs/runbook-rag-index.md`

**New (Phase F Slack, 6):**
- `bot_core.py` — channel-agnostic logic (extracted in Phase C)
- `slack_bridge.py`
- `slack_install.py`
- `firestore_slack.py`
- `slack_app_manifest.yaml`
- `com.shawn.email-cloudflared.plist`
- `docs/runbook-slack-channel.md`

**Modified (small additive changes only):**
- `watcher.py` — 1 hook in `process_user`, plus attachment loop for Phase B.6.
- `digest.py` — 1 hook (already on `gemma4:e4b`).
- `ppt.py` — 1 hook.
- `bridge.py` — Phase C: refactored to thin Telegram wrapper around `bot_core.py` + `orchestrator.py`.
- `schemas.py` — add `RAGQuery`, `LeadFilter`, `SlackEvent` validators.
- `gdpr_local_cleanup.py` — delete embeddings + revoke Slack tokens.
- `retention_sweep.py` — TTL on embeddings collection.
- `firestore.rules` — read rule for embeddings; Slack token isolation.
- `firestore.indexes.json` — composite index.
- `requirements.txt` — vector store dep, `slack-bolt`, multimodal dependencies.
- `deploy.sh` — `ollama pull embeddinggemma` + Cloudflare Tunnel install.
- `PRIVACY.md`, `SECURITY.md`, `test_pipeline.py`, `test_eval.py`.

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Gemma E-series tool-calling weaker than Llama → bot misroutes | Phase A.5 smoke test (decision gate). Hybrid orchestration is the default path; fall back to slash-command-only if even hybrid scores poorly. |
| `embeddinggemma` quality lower than expected | Track recall@5 in Phase D; one-line swap to `nomic-embed-text` or `mxbai-embed-large` (bumps dim to 1024 and requires reindexing — `embeddingVersion` field handles this). |
| Firestore Vector Search is still preview-flavored | All access behind `firestore_embeddings.py` (or `vector_store.py`); FAISS is a real alternative selected at Phase A gate, not a someday-maybe. |
| Embedding inversion (theoretical: vectors leak source text) | Per-user isolation via security rules. Treated with same retention/deletion guarantees as source email summary. **Note:** the v1 claim that summaries reduce inversion surface is wrong — summaries explicitly state key facts. We do not lean on that argument. |
| Backfill cost/load on Mac Mini | Backfill script is rate-limited + resumable + nightly batch; respects `embeddingVersion` so re-indexing is selective, not full-corpus. |
| Mac Mini single-point-of-failure widens with more state | Pre-existing concern — addressed in operator-controls runbook (Secret Manager / WIF migration). FAISS path concentrates state further; Firestore path spreads it. Factor into Phase A gate. |
| Slack Events API needs public HTTPS endpoint | Cloudflare Tunnel (free, no port-forwarding). If tunnel goes down, Telegram path still works as fallback. |
| Slack OAuth + workspace mapping more complex than Telegram | Mirror existing Telegram link-token UX: portal generates one-time claim code, user pastes into Slack DM with the bot. Same Pydantic boundary validation. |
| Gemma vision (Phase B.6) hallucinates on low-quality scans | Caption prompt explicitly asks for "extractable facts." Vision chunks marked `chunkType='attachment'` so eval can score them separately and we can lower their retrieval weight if they prove noisy. |
| Two models loaded simultaneously (Gemma + Llama) → RAM pressure | Both fit comfortably in 32GB Mac Mini at the chosen quantizations (~10GB combined active). On a 16GB host, hybrid path is not viable — fall back to slash-command-only. See §10 hardware section. |
| Slack App Directory review (if distributed publicly) | Out of scope for v1 — pilot uses internal-distribution install URLs. Revisit when going GA. |

---

## 10. Hardware Reality-Check

Pin model variants and quantizations explicitly so the plan is reproducible:

| Model | Tag | Quantization | Disk | Active RAM at inference |
|---|---|---|---|---|
| Generation / synthesis / vision | `gemma4:e4b` | default Q4 (Ollama default) | ~4GB | ~5–6GB (MatFormer keeps active params low) |
| Tool-routing | `llama3.1:8b` | Q4_K_M | ~5GB | ~5GB |
| Embedding | `embeddinggemma` | default | ~600MB | ~1GB |
| **Combined hybrid path peak** | — | — | ~10GB | **~10–12GB** |

**Mac Mini deployment:**
- 32GB RAM unified memory: comfortable. Hybrid path is the default.
- 16GB RAM: hybrid path is not viable. Drop to slash-command-only routing (single model, `gemma4:e4b`).
- 8GB RAM: this plan does not target 8GB hosts.

Ollama's keep-alive lets the second model warm-load while the first is in flight, but cold-start a 5GB model takes ~3s on Apple Silicon — budget that into the routing-step latency for the first request after idle.

---

## 11. Decisions (Confirmed 2026-04-29)

1. **Backfill scope:** ALL historical leads across every linked user. Rate-limited, resumable, off-hours batch. (Carried over from v1.)
2. **Bot routing:** Hybrid model orchestration is the working assumption.
   - `route_intent()` → `llama3.1:8b` (already pulled).
   - `synthesize()` → `gemma4:e4b`.
   - **Phase A.5 smoke test gates this.** If Gemma scores ≥80% on the 10-prompt routing eval, drop the Llama side and go single-model.
   - `/ask <question>` skips routing entirely → forces RAG path.
3. **Eval set:** 60 questions across 4 categories (Direct / Cross-corpus / Mixed / Multimodal). User sanity-checks expected answers in Phase D.
4. **Channels:** Telegram in v1; Slack added in Phase F, after Phase C is stable.
5. **Multimodal:** YES — Phase B.6 indexes image attachment captions. This is a deliberate exploitation of `gemma4:e4b`'s native vision capability, treated as a real product feature, not a research excursion.
6. **Vector store:** Firestore Vector Search by default; FAISS-on-disk + nightly GCS snapshot is a live alternative chosen at Phase A decision gate.
7. **Re-embed strategy:** `embeddingVersion` field makes selective re-indexing trivial when the summary prompt or embedding model changes.

Next step (only on green light): run **Section 7's smallest first slice** — a 1–2 hour smoke test confirming `embeddinggemma`, `gemma4:e4b` vision, and the chosen vector store all work end-to-end on the Mac Mini before any production code is written.

---

*Last updated: 2026-04-29 — supersedes `RAG_IMPLEMENTATION_PLAN.md` (v1, 2026-04-28) for execution. v1 retained as historical baseline; the deltas captured in §0 are the diff that justifies v2.*
