# rag_service — folder-scoped RAG over HTTP

Thin FastAPI wrapper around `rag_core.answer_question` so the Shomery web app
can ask grounded questions against a user's email folder. The Telegram bridge
keeps using `rag_core` directly and is unaffected.

- Single endpoint: `POST /ask` (Firebase ID token in `Authorization: Bearer …`)
- Liveness: `GET /healthz`
- LLM provider is swappable via one env var (`LLM_PROVIDER`) — same
  OpenAI-compatible client class works for Ollama, OpenAI, Anthropic, Gemini.

## Pilot deployment shape

```
[ shomery-web (Firebase Hosting) ]
            │  HTTPS, Bearer <Firebase ID token>
            ▼
[ Cloudflare Tunnel: rag.shomery.example ]
            │
            ▼
[ Mac Mini: python -m rag_service  ──►  Ollama (localhost:11434) ]
            │
            └─► Firestore (database "email2ppt") via firebase-admin
```

The Mac Mini already runs the watcher, embeddings, and Telegram bridge against
the same Firestore DB and Ollama instance — `rag_service` shares all of that.

## Environment variables

Read once at startup via `rag_service.config.get_config()`. Missing required
keys for the selected provider crash the process — no silent 500s.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `LLM_PROVIDER` | no | `ollama` | One of `ollama`, `openai`, `anthropic`, `gemini` |
| `RAG_PORT` | no | `8001` | uvicorn bind port |
| `RAG_CORS_ORIGINS` | no | `http://localhost:3000,https://shomeryai.web.app` | comma-separated |
| `OLLAMA_BASE_URL` | provider=ollama | `http://localhost:11434/v1` | Must end in `/v1` |
| `OLLAMA_MODEL` | provider=ollama | `llama3.1:8b` | |
| `OPENAI_API_KEY` | provider=openai | — | |
| `OPENAI_MODEL` | no | `gpt-4o-mini` | |
| `ANTHROPIC_API_KEY` | provider=anthropic | — | |
| `ANTHROPIC_MODEL` | no | `claude-haiku-4-5` | |
| `GEMINI_API_KEY` | provider=gemini | — | |
| `GEMINI_MODEL` | no | `gemini-2.0-flash` | |
| `GOOGLE_APPLICATION_CREDENTIALS` | yes | — | Path to `firebase-service-account.json` (used by `firestore_activity.get_db()` and Firebase Auth verification) |

## Running locally

From the repo root:

```bash
# 1. Make sure Ollama is up and the model is pulled
ollama serve &                # if not already running
ollama pull llama3.1:8b

# 2. Point the service at the Firebase service account
export GOOGLE_APPLICATION_CREDENTIALS="$PWD/firebase-service-account.json"

# 3. Launch
venv/bin/python -m rag_service
# → uvicorn on http://0.0.0.0:8001
```

Smoke test:

```bash
curl http://localhost:8001/healthz
# {"ok": true, "provider": "ollama", "model": "llama3.1:8b"}
```

A real `/ask` request needs a Firebase ID token from a signed-in web user;
test it from the browser with the web app pointed at `RAG_BASE_URL=http://localhost:8001`.

## Tests

```bash
venv/bin/python -m pytest tests/test_rag_service_main.py -v
```

The tests stub the Firestore handle, the LLM client, and the auth dependency
via `app.dependency_overrides` — no Ollama / Firebase / Firestore needed.

## Exposing the Mac Mini (Cloudflare Tunnel)

Stable HTTPS hostname without opening ports on the home router.

```bash
brew install cloudflared
cloudflared tunnel login
cloudflared tunnel create shomery-rag
# add a DNS route for the tunnel, e.g.:
cloudflared tunnel route dns shomery-rag rag.shomery.example
```

`~/.cloudflared/config.yml`:

```yaml
tunnel: shomery-rag
credentials-file: /Users/<you>/.cloudflared/<tunnel-uuid>.json
ingress:
  - hostname: rag.shomery.example
    service: http://localhost:8001
  - service: http_status:404
```

Run as a launchd service so it survives reboots:

```bash
sudo cloudflared service install
```

Then set `RAG_BASE_URL=https://rag.shomery.example` in the Shomery web app's
production environment. The web app already sends Firebase ID tokens; CORS is
gated by `RAG_CORS_ORIGINS`.

## Swapping providers (Mac Mini → cloud)

The whole point of the `LLM_PROVIDER` switch: zero code change to migrate.

1. Stop the service.
2. Set the new env vars (e.g. for Anthropic):
   ```bash
   export LLM_PROVIDER=anthropic
   export ANTHROPIC_API_KEY=sk-ant-…
   export ANTHROPIC_MODEL=claude-haiku-4-5
   ```
3. Start the service again. `/healthz` now reports the new provider/model.

Internals: `rag_service.llm_config.build_llm_client()` returns an
`openai.OpenAI` client pointed at the right `base_url` for the provider.
`rag_core.grounded_answer` accepts that client via `llm_client=`, so the same
code path serves all four providers. Embeddings still use the local Ollama
embedding model — only the chat completion provider changes.

When the cloud migration happens for real, the deploy target also moves off
the Mac Mini (Cloud Run / Fly / Render — anything that runs a Python container).
The service code itself does not need to change.
