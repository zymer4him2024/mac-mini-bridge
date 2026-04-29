# RAG + Multi-Channel Companion — Implementation Plan

*Adds a vector-indexed corpus, RAG-powered answers, and a second delivery channel (Slack) to your existing multi-tenant email2ppt pipeline. Purely additive — no rewrites.*

---

## 1. Decisions Locked In

| Decision | Choice | Why it matters |
|---|---|---|
| AI for embeddings + chat | **All-local Ollama** (`nomic-embed-text` + `llama3.1:8b`) | Preserves your KMS/GDPR/local-first posture. No data leaves the Mac Mini. |
| Vector store | **Firestore Vector Search** | Native to your stack; per-user isolation maps to existing `users/{uid}/...` pattern. |
| Delivery surface | **Telegram (v1) + Slack (Phase F)** | Telegram for power users / dogfood. Slack added because that's where US SMB customers actually live. Portal at `apps/email2ppt-portal` stays untouched in this plan. |

---

## 2. What You Already Have (Do Not Rebuild)

```
✅ Multi-tenant pipeline (per-user Gmail OAuth, Firestore-stored)
✅ watcher.py     — 5-min poll, summarize, PDF, lead upsert, Telegram alert
✅ digest.py      — 7am daily roll-up
✅ ppt.py         — on-demand deck from Gmail query
✅ bridge.py      — Telegram bot ↔ Ollama with Gmail tools
✅ firestore_leads.py / firestore_users.py / firestore_telegram.py
✅ KMS envelope encryption, log redaction, audit, GDPR cleanup, retention sweeps
✅ Pydantic schemas at Telegram boundary
✅ launchd plists for all jobs
✅ CI: ruff + bandit + mypy strict + gitleaks + pre-commit
```

The bot today is **agent-with-Gmail-tools**: it dynamically calls `search_emails` / `read_email` / `create_draft` against live Gmail. That works for "find me unread from Bob" but loses on cross-corpus questions and re-fetches Gmail every query.

---

## 3. What's Being Added

```
+ Ollama: pull nomic-embed-text (768-dim, local)
+ Firestore: new collection users/{uid}/embeddings/{id} with vector field
+ embeddings.py            — Ollama embedding wrapper, retries, redaction
+ firestore_embeddings.py  — upsert / search / per-user delete
+ Hooks (1 line each)      — watcher.py, digest.py, ppt.py
+ bot_core.py              — channel-agnostic bot logic (extracted from bridge.py)
+ bridge.py                — refactored to thin Telegram I/O wrapper
+ slack_bridge.py          — Slack Bolt webhook + message-format adapter
+ slack_install.py         — OAuth install flow per workspace
+ firestore_slack.py       — workspace tokens (KMS-wrapped)
+ slack_app_manifest.yaml  — bot scopes, slash commands, event subscriptions
+ Cloudflare Tunnel        — secure public HTTPS for Slack Events API webhook
+ backfill_embeddings.py   — one-time index of existing leads
+ Updated GDPR + retention — wipe embeddings + Slack tokens on user delete
+ docs/runbook-rag-index.md, docs/runbook-slack-channel.md
+ Eval set: 20 Q&A pairs   — recall + answer-quality regression baseline
```

Total: 9 new files, ~14 files modified with small additive changes.

---

## 4. Data-Flow Map

```
   Gmail email
      │
      ▼
  watcher.py ── summarize_email() (Ollama llama3.1:8b)
      │                │
      │                ▼
      │      ┌─────────────────────┐
      │      │ NEW: index_for_rag()│
      │      │   ↓                  │
      │      │ embeddings.py        │
      │      │   ↓                  │
      │      │ firestore_embeddings │
      │      │   ↓                  │
      │      │ users/{uid}/         │
      │      │   embeddings/{id}    │
      │      │   - text (summary)   │
      │      │   - embedding (768d) │
      │      │   - leadId, msgId    │
      │      │   - sender, subject  │
      │      └─────────────────────┘
      ▼
  build_pdf() ─→ disk + Telegram (unchanged)
  upsert_lead() ─→ Firestore (unchanged)


   Telegram message
      │
      ▼
  bridge.py — Ollama chooses tool:
      ├─ search_emails / read_email   (live Gmail, unchanged)
      ├─ create_draft                  (unchanged)
      ├─ NEW: rag_search(q, k=5)      (vector retrieval over corpus)
      └─ NEW: query_leads(filter)     (structured Firestore query)
      │
      ▼
  Reply with citations:
   "Per lead Acme (3 emails, last 2026-04-25): they want…"
```

---

## 5. New Data Model

**Collection:** `users/{uid}/embeddings/{embedding_id}`

| Field | Type | Notes |
|---|---|---|
| `embedding` | `Vector(768)` | nomic-embed-text output. Firestore vector field. |
| `text` | string | The text that was embedded — typically the LLM-generated summary, NOT raw email body. (Summaries already pass through your pipeline; treated with same care as source.) |
| `chunkType` | enum | `summary` \| `subject` \| `digest` |
| `leadId` | string | Joins to `users/{uid}/leads/{leadId}` |
| `messageId` | string | Gmail msg ID — dedup key + can refetch source |
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
- `ollama pull nomic-embed-text` on Mac Mini
- Create Firestore vector index (one-time gcloud command)
- Build `embeddings.py` (~80 lines)
- Build `firestore_embeddings.py` (~120 lines)
- Update `firestore.rules` + rules tests
- Unit tests for both modules

**Done when:** `python -c "from embeddings import embed_text; print(embed_text('hello').shape)"` returns 768-dim, and a roundtrip write/query against Firestore returns the seeded doc.

---

### Phase B — Indexing (2–3 days)
- Add `index_for_rag(uid, email, summary, lead_id)` helper (best-effort, never raises — same pattern as `upsert_lead`)
- Hook into `watcher.py` after `summarize_email()` (1 line)
- Hook into `digest.py` (1 line, dedup by messageId)
- Hook into `ppt.py` (1 line, dedup by messageId)
- Update `gdpr_local_cleanup.py` and `retention_sweep.py` to also delete embeddings
- Build `backfill_embeddings.py` — walks **all historical leads** across every linked user. Embeds each lead's `lastSummaryResponse` + subject. Idempotent (skip if `messageId` already indexed), resumable (writes a checkpoint per user), rate-limited (configurable QPS to Ollama and Firestore), and intended to run as an overnight launchd one-shot. Logs progress every 100 docs; emits a final per-user summary.
- Tests in `test_pipeline.py`

**Done when:** A new email arrives → 30s later it's queryable from a Python REPL via `firestore_embeddings.search_embeddings(uid, "test query")`.

---

### Phase C — RAG retrieval in the bot (2–3 days)
- Add `rag_search(question, k=5)` to `TOOLS` in `bridge.py`
  - Embeds the question, queries Firestore vector index scoped to current user, returns chunks + metadata
- Add `query_leads(filter)` for structured aggregations ("how many manufacturing leads")
- Update system prompt:
  - "What did X say about Y" → prefer `rag_search`
  - "Find emails matching ..." → use `search_emails`
  - "Count / list / how many" → use `query_leads`
  - Always cite: "Source: lead Acme, 2026-04-25"
- Add Telegram command `/ask <question>` as an explicit RAG-first path (forces `rag_search` + `query_leads`, skips Gmail tool calls). Plain messages keep the existing auto-route — Ollama picks among the full toolset (`search_emails`, `read_email`, `create_draft`, `rag_search`, `query_leads`) guided by the new system prompt
- Update Pydantic `schemas.py` with `RAGQuery` validator (length + char class)

**Done when:** "What did Acme say about pricing?" via Telegram returns a sourced answer pulled from your indexed summaries (not Gmail re-fetch).

---

### Phase D — Eval & tuning (1–2 days)
- Build 20-question eval set across 3 categories:
  - Direct lookup ("status of Acme deal?")
  - Cross-corpus aggregation ("manufacturing leads with budget")
  - Mixed ("most recent Acme email + summarize last 3 emails from them")
- Sanity-check expected answers with you
- Run baseline (Gmail-tools only) vs RAG-augmented
- Tune retrieval `k`, prompt, dedup logic
- Track recall@5 and citation accuracy in `test_eval.py`

**Done when:** ≥80% of eval questions return a correct, cited answer.

---

### Phase E — Docs (0.5 day)
- New: `docs/runbook-rag-index.md` (creating index, monitoring, rotation)
- Update `PRIVACY.md`: embeddings collection lifecycle, retention, deletion
- Update `SECURITY.md`: vector store threat model, embedding inversion notes

---

### Phase F — Slack channel (3–4 days, **after Phase C lands**)
**Goal:** Add Slack as a second delivery channel sharing the same RAG/Ollama backend, so US SMB customers can use the bot inside the workspace they already live in.

**Architecture:**
- **Refactor first:** Extract channel-agnostic logic from `bridge.py` into `bot_core.py`. This is a behavior-preserving move — `ask_llm()`, the TOOLS list, `execute_tool()`, system prompts all live in `bot_core.py`. `bridge.py` becomes a thin Telegram I/O wrapper. Slack gets its own thin wrapper.
- **Reachability:** Telegram works via outbound long-poll (no public IP needed). Slack Events API is webhook-based — Slack POSTs to your endpoint, so the Mac Mini needs a public HTTPS URL. Use **Cloudflare Tunnel** (free, no port-forwarding, fits the local-first ethos). Endpoint: `https://email2ppt.<your-domain>/slack/events`.
- **Multi-tenancy:** Slack install is per *workspace*; map each workspace install to a `users/{uid}` document via the OAuth `installer.user_id` and an explicit "claim this install" step on the portal. Slack tokens stored at `users/{uid}/secrets/slack` with the existing KMS envelope wrap.

**Steps:**
1. Refactor `bridge.py` → `bot_core.py` + thin Telegram wrapper. No behavior change. Tests must pass before moving on.
2. Create Slack app via manifest (`slack_app_manifest.yaml`): bot scopes (`chat:write`, `app_mentions:read`, `im:history`, `im:write`, `commands`); slash command `/ask`; Events API subscriptions (`message.im`, `app_mention`).
3. Build `slack_install.py` — OAuth install flow, request signature verification, workspace ↔ user mapping.
4. Build `firestore_slack.py` — token CRUD with KMS wrapping (mirror existing `firestore_telegram.py` pattern).
5. Build `slack_bridge.py` — Slack Bolt for Python (`slack-bolt` package), receives events, calls `bot_core.handle_message(uid, text)`, formats reply using Slack Block Kit (richer than Telegram's plain text).
6. Stand up Cloudflare Tunnel — `cloudflared` daemon as a launchd job, `com.shawn.email-cloudflared.plist`.
7. Add Pydantic validator `SlackEvent` for incoming payloads.
8. Update `gdpr_local_cleanup.py` to also revoke + delete Slack tokens.
9. New runbook `docs/runbook-slack-channel.md` — install steps, tunnel setup, troubleshooting.

**Done when:** A second user installs the Slack app to their workspace via the portal's "Add to Slack" link, claims the install, then DMs `/ask what's the status of Acme deal?` to the bot in Slack and gets the same sourced answer they'd get from Telegram.

---

**Total estimate: 10–14 working days of focused build (Phases A–F).**

---

## 7. Smallest First Slice (1–2 hours, before any plumbing)

Three sanity checks. If any fail, we replan before building.

```sh
# 1. Confirm Ollama embedding works locally
ollama pull nomic-embed-text
ollama list | grep nomic
python -c "
import requests
r = requests.post('http://localhost:11434/api/embeddings',
                  json={'model':'nomic-embed-text','prompt':'hello world'}).json()
print('dim =', len(r['embedding']))   # expect 768
"

# 2. Confirm Firestore Vector Search write/query works
python smallest_first_slice.py     # script I'll write — seeds 3 docs, queries

# 3. End-to-end with one real lead
python -c "
from firestore_users import enumerate_linked_users
from firestore_leads import _lead_id  # reuse your hash
# pull one existing lead's lastSummaryResponse
# embed it, write to test collection, query, print closest match
"
```

If those three return clean output, the rest is plumbing.

---

## 8. Files Changed

**New (Phases A–E, 4):**
- `embeddings.py`
- `firestore_embeddings.py`
- `backfill_embeddings.py`
- `docs/runbook-rag-index.md`

**New (Phase F Slack, 6):**
- `bot_core.py` — extracted channel-agnostic logic
- `slack_bridge.py`
- `slack_install.py`
- `firestore_slack.py`
- `slack_app_manifest.yaml`
- `com.shawn.email-cloudflared.plist`
- `docs/runbook-slack-channel.md`

**Modified (small additive changes only):**
- `watcher.py` — 1 hook in `process_user`
- `digest.py` — 1 hook
- `ppt.py` — 1 hook
- `bridge.py` — Phase C: 2 tool definitions + system prompt + `/ask` handler. Phase F: refactored to thin Telegram wrapper around `bot_core.py`.
- `schemas.py` — add `RAGQuery` and `SlackEvent` validators
- `gdpr_local_cleanup.py` — delete embeddings + revoke Slack tokens on user wipe
- `retention_sweep.py` — TTL on embeddings collection
- `firestore.rules` — read rule for embeddings; Slack token isolation
- `firestore.indexes.json` — composite index
- `requirements.txt` — Firestore vector dep + `slack-bolt`
- `deploy.sh` — `ollama pull nomic-embed-text` + Cloudflare Tunnel install
- `PRIVACY.md`, `SECURITY.md`, `test_pipeline.py`

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `nomic-embed-text` quality lower than cloud embeddings | Track recall@5 in eval; switch to `mxbai-embed-large` (1024-dim) if recall <70% |
| Firestore Vector Search is still preview-flavored | Keep all index access behind `firestore_embeddings.py` so swap to pgvector/Pinecone is a one-file change |
| Embedding inversion attacks (theoretical: vectors leak source text) | Per-user isolation via security rules; embeddings are derived from already-summarized text, not raw email bodies |
| Backfill cost/load on Mac Mini | Backfill script is rate-limited + resumable + nightly batch by default |
| Mac Mini single-point-of-failure widens with more state | Pre-existing concern — addressed in your operator-controls runbook (WIF migration) |
| Slack Events API needs public HTTPS endpoint | Cloudflare Tunnel (free, no port-forwarding, no public IP exposed). If tunnel goes down, Telegram path still works as fallback. |
| Slack OAuth + workspace mapping is more complex than Telegram | Mirror your existing Telegram link-token UX: portal generates a one-time claim code, user pastes into Slack DM with the bot to bind workspace ↔ user account. Same Pydantic boundary validation. |
| Slack Block Kit rich formatting may diverge from Telegram plain text | `bot_core.py` returns structured response objects; each channel adapter renders to its own format. Single source of truth for content. |
| Slack App Directory review (if you ever distribute publicly) | Out of scope for v1 — pilot uses internal-distribution install URLs, no review needed. Revisit when you go GA. |

---

## 10. Decisions (Confirmed 2026-04-28)

1. **Backfill scope:** ALL historical leads across every linked user. `backfill_embeddings.py` will be rate-limited, resumable, and run as an off-hours batch — see Phase B note below.
2. **Bot routing:** Both modes wired in:
   - `/ask <question>` → explicit RAG-first path (skips Gmail tools, prefers `rag_search` + `query_leads`).
   - Plain messages → bot auto-routes via Ollama tool-choice over the full toolset (`search_emails`, `read_email`, `create_draft`, `rag_search`, `query_leads`). System prompt nudges intent recognition; the LLM picks.
3. **Eval set:** I draft 20 questions from your real lead data; you sanity-check expected answers in Phase D before we tune.
4. **Channels:** Telegram in v1; Slack added in **Phase F**, after Phase C (RAG retrieval) is stable. Slack chosen as the second channel because it's where US SMB customers actually work, costs nothing (vs SMS/WhatsApp which scale to real money per message), and reuses the same RAG backend.

Next step (only on your green light): run **Section 7's smallest first slice** — a 1–2 hour smoke test confirming Ollama embeddings + Firestore Vector Search work end-to-end on your Mac Mini before any production code is written.

---

*Last updated: 2026-04-28 — Phase F (Slack channel) added per Shawn's request. Supersedes the earlier `email2ppt/IMPLEMENTATION_PLAN.md` draft, which assumed greenfield.*
