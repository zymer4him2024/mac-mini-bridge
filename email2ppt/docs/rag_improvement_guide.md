# RAG Improvement Guide

A reference for improving Retrieval-Augmented Generation, with notes on how each technique applies to email2ppt's stack (Ollama local, Firestore Vector Search, Telegram-only v1).

---

## 1. Fix Retrieval First (highest ROI)

### Chunking strategy
Naive 512-token splits destroy meaning. Better options:
- **Recursive character splitting** — respects paragraph/sentence boundaries.
- **Semantic chunking** — split where embedding similarity drops between sentences.
- **Structure-aware chunking** — split on Markdown headers, HTML sections, code blocks.

**For email2ppt:** Chunk by message boundaries. Keep `subject` + `sender` + `received_at` as metadata. Never split a single message. PDF summaries chunk by section heading.

### Hybrid search
Pure vector search misses exact terms (names, IDs, error codes). Combine dense embeddings with sparse retrieval (BM25 / SPLADE) and fuse with **Reciprocal Rank Fusion (RRF)**. Single biggest "free" recall improvement.

**For email2ppt:** Firestore doesn't have native BM25, but you can run a lightweight BM25 index in Python (e.g., `rank_bm25`) over the same chunks and merge with RRF.

### Re-ranking
Retrieve top 50–100 with cheap retrieval, then re-rank with a cross-encoder. Keep top 5–10 for the final prompt.

- **Cross-encoders:** Cohere Rerank, BGE-reranker-v2, Jina Reranker, mxbai-rerank.
- **LLM-as-judge:** ask Ollama to score each chunk's relevance to the query.

**For email2ppt:** BGE-reranker-v2-m3 runs locally; or use Ollama with a small model (qwen2.5:3b) as a relevance scorer.

### Metadata filtering
Pre-filter on metadata *before* vector search. Massive precision gains.

**For email2ppt:** Filter by `tenant_id`, `project_id`, `subject_id`, `sender`, `date_range` first — then semantic search inside that subset. Your three-level Project → Subject → Topic hierarchy is exactly the right metadata schema.

### Better embeddings
- Hosted: OpenAI `text-embedding-3-large`, Voyage-3, Cohere Embed v3.
- Local: BGE-M3, E5-Mistral, `nomic-embed-text` (Ollama), `mxbai-embed-large`.
- Domain fine-tuning on your own (query, relevant_doc) pairs typically beats any generic model.

**For email2ppt:** `nomic-embed-text` is your planned default — fine. `bge-m3` is stronger for multilingual and longer context if needed.

---

## 2. Fix the Query Before Retrieval

| Technique | What it does | When to use |
|---|---|---|
| Query rewriting | Expand short user queries with synonyms / terms | Always — cheap |
| HyDE | LLM generates fake answer; embed *that* and search | Short queries on technical corpora |
| Multi-query | Generate 3–5 paraphrases; retrieve for each; dedupe | High-stakes recall |
| Step-back prompting | Ask broader question first, narrow after | Specific factual questions |
| Query routing | Classify query type → different pipeline per type | Mature systems with mixed query types |

**For email2ppt:** Start with query rewriting (cheap, always-on). Add routing later: "summarize" queries → fetch full thread; "find" queries → vector search; "count/aggregate" queries → Firestore SQL-like queries on `lead_tracker`.

---

## 3. Fix What You Index

### Parent-document / sentence-window retrieval
Index small chunks for precise matching, but return the *larger surrounding context* to the LLM. (LlamaIndex calls this "auto-merging.")

### Hierarchical / summary indexing
Build a tree: doc summary → section summary → chunk. Retrieve top-down.

### Document enrichment ("Contextual Retrieval")
Anthropic's published technique: at index time, prepend a short LLM-generated context to each chunk before embedding (e.g., "This chunk is from an email from Acme Corp on 2026-03-15 about pricing for Project Falcon"). Big recall gains for ~50 tokens per chunk.

**For email2ppt:** This is your highest-leverage indexing improvement. Cheap to add (one Ollama call per chunk at index time), big quality jump for cross-thread queries.

### Knowledge graphs (GraphRAG)
Microsoft's GraphRAG extracts entities/relationships, builds a graph, and uses community summaries. Best for "find connections across many docs" queries.

**For email2ppt:** Defer. Worth revisiting once you have enough lead history that "show me everyone who mentioned competitor X" becomes a real query.

### Multi-vector indexing
Index multiple representations of the same chunk: raw, summary, generated questions, entities only. Embed each separately.

---

## 4. Smarter Retrieval Loops

| Pattern | What it does |
|---|---|
| **Self-RAG** | Model decides *whether* to retrieve, retrieves, then critiques relevance |
| **CRAG** | Lightweight evaluator scores results; falls back if low confidence |
| **Adaptive RAG** | Router classifies complexity → simple LLM, RAG, or multi-hop agent |
| **FLARE** | Generate sentence → check confidence → retrieve only when uncertain |
| **Agentic RAG** | Treat retrieval as a tool the agent calls iteratively |

**For email2ppt:** Your existing `bridge.py` is already an agentic pattern (Gmail as tools). Adding RAG = adding `search_indexed_history` as another tool the agent can call. This is the cleanest evolution path — no rewrite.

---

## 5. Generation-Side Improvements

- **Context compression** (LLMLingua) — drop irrelevant tokens before sending to LLM. Saves cost, reduces "lost in the middle."
- **Citation discipline** — force the model to cite chunk IDs. Reduces hallucination, gives debuggability.
- **Position-aware prompting** — put most relevant chunks at start *and* end of context. LLMs attend better there.

---

## 6. Evaluation (the part everyone skips)

You can't improve what you don't measure. Build an eval set of (query, ideal_answer, ideal_context) tuples — even 50 hand-curated examples beats nothing.

**Frameworks:**
- **RAGAS** — faithfulness, answer relevance, context precision, context recall.
- **TruLens** — production tracing.
- **DeepEval** — pytest-style RAG tests.
- **Phoenix / Arize** — observability.

Track per-stage metrics. Most "the LLM is dumb" complaints turn out to be retrieval failures, not generation failures.

**For email2ppt:** Build a 50-example eval set from real queries you've run through `bridge.py`. Track recall@10 (retrieval) and faithfulness (generation) separately.

---

## 7. Alternatives to RAG (or hybrid)

| Approach | When it wins | When it loses |
|---|---|---|
| **Long-context models** (Claude 200K, Gemini 2M) | Corpus < 500K tokens, low query volume | Cost per query, retrieval still helps for accuracy |
| **Cache-Augmented Generation (CAG)** | Small, stable corpus | Anything that updates frequently |
| **Fine-tuning** | Stable knowledge, tone, terminology | Frequently-changing data |
| **RAFT** | You have training data, want best of both | Cold start |
| **Tool use (SQL/API)** | Structured data | Unstructured prose |
| **Memory systems** (mem0, Letta, Zep) | User-specific evolving knowledge | Static doc Q&A |
| **Hybrid SQL + vector + graph** | Production systems with mixed data | Early-stage / simple needs |

**For email2ppt:** Your `lead_tracker` is structured — query it with Firestore queries, not vector search. Email bodies and PDF summaries are unstructured — vector index those. This split is the single most important architectural decision.

---

## 8. Production Concerns

- **Latency:** ANN indexes (HNSW, IVF), embedding caches, async retrieval.
- **Cost:** Smaller embedding model for indexing, larger for queries; cache embeddings of frequent queries.
- **Freshness:** Incremental indexing, change-data-capture on new emails.
- **Privacy:** On-device embeddings (you're already doing this with Ollama — good).
- **Observability:** Log every (query, retrieved_chunks, answer) trace. This becomes your fine-tuning data.

---

## 9. Multi-Channel Modularization (architecture concern)

**Decision:** the RAG core must be channel-agnostic. Telegram is just the first front-end. Slack, WhatsApp, the web portal, and a third-party REST API will all sit on top of the same RAG service.

### The three layers

```
┌─────────────────────────────────────────────────────────────┐
│  CHANNEL ADAPTERS                                            │
│  Telegram  │  Slack  │  Web (SSE)  │  WhatsApp  │  REST API  │
│  (bridge.py — becomes the Telegram adapter)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼  (uniform call signature)
┌─────────────────────────────────────────────────────────────┐
│  RAG SERVICE  (rag/ package)                                 │
│  rag.answer(query, auth_ctx, options) → RagResponse          │
│  rag.stream(query, auth_ctx, options) → AsyncIterator        │
│  Internals: rewrite → filter → search → rerank → generate    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STORAGE                                                     │
│  Firestore Vector Search  +  Lead Tracker  +  Email PDFs     │
└─────────────────────────────────────────────────────────────┘
```

### Contracts (what each layer must guarantee)

**1. The auth context object** (populated by each adapter, identical shape):

```python
@dataclass(frozen=True)
class AuthContext:
    tenant_id: str         # mandatory — drives all metadata filters
    user_id: str           # who is asking (for audit)
    channel: str           # "telegram" | "slack" | "web" | "rest" | ...
    session_id: str | None # thread/chat id for multi-turn memory
    scopes: list[str]      # what this caller is allowed to query
```

**2. The response shape** (channel-agnostic):

```python
@dataclass
class Citation:
    chunk_id: str
    source_type: str        # "email" | "pdf_summary" | "lead_record"
    source_ref: str         # gmail_id, pdf_path, lead_id
    snippet: str            # short excerpt
    received_at: datetime | None

@dataclass
class RagResponse:
    answer: str             # plain text (markdown allowed)
    citations: list[Citation]
    confidence: float       # 0.0 – 1.0, from reranker scores
    metadata: dict          # latency, model, retrieved_count, etc.
```

Adapters render this however suits their channel: Telegram = single Markdown message with inline citations; Slack = blocks with citation buttons; Web = streaming JSON with rich citation cards.

**3. Streaming vs single-shot.** Expose two entry points:
- `rag.answer(...)` — returns full `RagResponse`. Used by Telegram, WhatsApp, REST.
- `rag.stream(...)` — async iterator yielding partial answer + final citations. Used by web portal (SSE) and any future low-latency UI.

### What this means for the v1 → v3 plan (revised)

**v1 (ship first):**
1. Build `rag/` package with `service.py`, `retrieval.py`, `generation.py`, `schemas.py`, `auth.py`.
2. Chunk emails by message boundary; chunk PDF summaries by heading.
3. Index with `nomic-embed-text` via Ollama → Firestore Vector Search through `firestore_vectors.py` wrapper.
4. Metadata: `tenant_id`, `project_id`, `subject_id`, `sender`, `received_at`.
5. Implement `rag.answer()` end-to-end (filter → vector search top-20 → llama3.1:8b → citations).
6. Refactor `bridge.py` to be the **Telegram adapter** — it builds `AuthContext` from chat_id and calls `rag.answer()`. No RAG logic stays in `bridge.py`.
7. Write a contract test suite that any adapter must pass (`tests/adapters/contract_test.py`).

**v2 (quality + second adapter):**
8. Add contextual retrieval (prepend Ollama-generated context per chunk at index time).
9. Add BGE reranker (top-50 → top-10).
10. Add query rewriting.
11. Implement **REST API adapter** (`api/rag_endpoint.py`, FastAPI) — proves the abstraction works. Auth via API key → `AuthContext`.
12. Build 50-query eval set; track recall@10 and faithfulness across adapters.

**v3 (scale + more channels):**
13. Implement `rag.stream()` for SSE.
14. Build **web portal adapter** (uses streaming).
15. Build **Slack adapter** (uses single-shot, formats as blocks).
16. Add hybrid sparse retrieval (`rank_bm25`) + RRF fusion.
17. Route query types (summarize / find / count) to different sub-pipelines inside `rag.answer()`.

### Rules to enforce now (cheap to do, expensive to retrofit)

- **No channel-specific code inside `rag/`.** No mention of Telegram, Slack, chat IDs, message formatting, or rate limits in the service layer. Adapters handle all of that.
- **No direct Firestore SDK imports outside the `firestore_*.py` wrappers** (existing rule extended to vector store).
- **Tenant isolation is the service layer's job, not the adapter's.** Adapters supply `tenant_id`; the service applies it as a metadata filter on every query. Never trust the adapter to scope the search itself.
- **Every adapter must pass the contract test suite** before being merged. Same input → same `RagResponse` shape, regardless of channel.
- **Channel-specific concerns** (rate limits, message length, attachment handling, conversational state) live in the adapter only.
- **Audit logging** happens in the service layer so it's uniform across channels.

This adds maybe 1–2 days of extra work in v1 and saves 1–2 weeks per future channel.

---

## 10. Model Provider Abstraction (architecture concern)

**Decision:** Just as channel adapters abstract the front-end, **LLM provider adapters** abstract the back-end. The RAG service must be able to call any local or cloud model through a uniform interface, with per-stage and per-tenant model selection.

### Why this matters

- **Capability matching.** Different RAG stages need different model strengths. Generation needs faithfulness; query rewriting needs speed; reranking needs precision. Forcing one model to do all three wastes cost or quality.
- **Privacy tiers.** Some tenants (or some data classifications) must stay local. Others allow cloud. The abstraction makes this a config switch, not a code change.
- **BYO-key.** Enterprise customers will want to use their own Anthropic / OpenAI / Azure keys for compliance and billing. The provider layer is where their key gets injected.
- **Cost / latency optimization.** Cheap fast model for the 80% of queries; premium model for the 20% complex ones. Routable inside the service.
- **Vendor risk.** Lock-in to one provider is a strategic risk. The adapter makes any provider replaceable.

### Three provider interfaces

```python
class LLMProvider(Protocol):
    async def chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> ChatResponse: ...

    async def stream(
        self,
        messages: list[Message],
        ...
    ) -> AsyncIterator[ChatChunk]: ...

class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[Vector]: ...
    @property
    def dim(self) -> int: ...
    @property
    def name(self) -> str: ...   # critical: index must record which model produced its vectors

class RerankerProvider(Protocol):
    async def rerank(
        self,
        query: str,
        docs: list[str],
        top_k: int,
    ) -> list[ScoredDoc]: ...
```

### Concrete providers (plan)

| Provider class | Backend | Use case |
|---|---|---|
| `OllamaLLMProvider` | local Ollama HTTP | v1 default — privacy, zero cost |
| `OpenAICompatLLMProvider` | any OpenAI-compatible endpoint | covers Ollama, vLLM, LM Studio, Together, Groq, Fireworks |
| `AnthropicLLMProvider` | Anthropic API | premium / BYO-key path |
| `GoogleLLMProvider` | Gemini API | long-context use cases |
| `OllamaEmbeddingProvider` | local | v1 default |
| `VoyageEmbeddingProvider` / `CohereEmbeddingProvider` | cloud | quality upgrade option |
| `BGERerankerProvider` | local | v2 default |
| `CohereRerankerProvider` | cloud | premium option |

Most cloud providers also expose an OpenAI-compatible endpoint, so a single `OpenAICompatLLMProvider` plus per-vendor specializations covers ~90% of real cases. Consider [LiteLLM](https://github.com/BerriAI/litellm) as the *implementation* behind your interface if you want to skip writing 8 adapters by hand — but keep the public interface yours, so the dependency is swappable.

### Per-stage, per-tenant configuration

Model selection is a config concern, not a code concern. Two layers of override:

```yaml
# config/rag_models.yaml — global defaults
defaults:
  generation:
    provider: ollama
    model: llama3.1:8b
  query_rewrite:
    provider: ollama
    model: qwen2.5:3b        # smaller, faster for helper calls
  embedding:
    provider: ollama
    model: nomic-embed-text
  rerank:
    provider: bge-local
    model: bge-reranker-v2-m3
  contextual_enrichment:
    provider: ollama
    model: qwen2.5:3b

# Per-tenant overrides (Firestore: tenants/{tenant_id}/rag_policy)
tenant_overrides:
  acme-corp:
    privacy_tier: local_only        # hard-blocks any cloud provider
  big-bank:
    generation:
      provider: anthropic
      model: claude-sonnet-4-6
      api_key_ref: kms://big-bank/anthropic-key   # BYO key
```

The service resolves the effective model per call:
`effective_model(stage, tenant) = tenant_overrides.get(stage) or defaults[stage]`

### Hard rules

- **Privacy tier is enforced inside the provider registry**, not in calling code. If a tenant's policy is `local_only`, the registry refuses to return a cloud provider, and the call fails closed.
- **The embedding model name is recorded in every vector record.** When you swap embedding providers, you must reindex — or the service must refuse to mix vectors from different models. (Different embeddings live in incompatible vector spaces.)
- **Tool-call formats are normalized at the provider boundary.** Anthropic, OpenAI, Gemini, and Ollama all use different tool schemas. The provider adapter translates a single internal `ToolSpec` into each vendor's format.
- **Every provider call is audit-logged**: tenant, stage, provider, model, latency, token counts, cost estimate. This is your data for both billing and optimization.
- **Streaming must work across all providers.** If a provider doesn't support streaming, the adapter buffers and yields the final result as a single chunk — caller doesn't have to care.
- **Fallback chains are explicit.** "Try Anthropic; on timeout/error, fall back to Ollama" is a config, not silent magic.

### Where this slots into the v1 → v3 plan (re-revised)

**v1 (ship first):**
1. Build `rag/` package with `service.py`, `retrieval.py`, `generation.py`, `schemas.py`, `auth.py`.
2. Build `rag/providers/` package with the three Protocol interfaces and the v1 implementations only:
   - `ollama_llm.py`, `ollama_embedding.py`
   - `provider_registry.py` (resolves per-stage / per-tenant)
3. Index pipeline + Telegram adapter (as before).
4. Refactor `bridge.py` to be the Telegram adapter; no RAG logic stays in it.

**v2 (quality + second adapter + cloud option):**
5. Add `OpenAICompatLLMProvider` (one adapter unlocks many providers — Ollama, Together, Groq, vLLM).
6. Add `AnthropicLLMProvider` (or rely on OpenAI-compat through their compat endpoint — check current support).
7. Add contextual retrieval (uses small helper model from registry — already abstracted).
8. Add `BGERerankerProvider`.
9. Add query rewriting.
10. REST API adapter (second channel).
11. Build 50-query eval set; **evaluate per-provider and per-model**, not just per-pipeline.

**v3 (scale + more channels + per-tenant policy):**
12. Streaming entry point (`rag.stream()`) — must be supported by every adapter and every provider.
13. Web portal adapter (SSE) and Slack adapter.
14. Per-tenant policy engine (Firestore-backed) — enables BYO-key, privacy tiers, fallback chains.
15. Hybrid sparse retrieval + RRF fusion.
16. Query routing (summarize / find / count → different sub-pipelines, possibly different models).

---

## Recommended Path for email2ppt — At a Glance

| Phase | Service / Adapter additions | Provider additions | Channels | Models |
|---|---|---|---|---|
| **v1** | RAG service + Telegram adapter + provider registry | Ollama LLM + Ollama embedding | Telegram | Local only |
| **v2** | Contextual retrieval, reranker, REST adapter | OpenAI-compat + Anthropic + BGE reranker | Telegram, REST | Local + cloud option |
| **v3** | Streaming, web + Slack adapters, per-tenant policy | Voyage / Cohere as options, fallback chains | Telegram, REST, Web, Slack | Per-tenant, per-stage, BYO-key |

---

*Last updated: 2026-04-29*
