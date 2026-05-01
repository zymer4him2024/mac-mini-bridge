"""Run the rag_service via `python -m rag_service`.

Binds 0.0.0.0 so a Cloudflare/Tailscale tunnel on the same host can reach
it. Production/pilot launches go through this entrypoint; tests construct
the FastAPI app directly via `from rag_service.main import app`.
"""

from __future__ import annotations

import uvicorn

from .config import get_config


def main() -> None:
    cfg = get_config()
    uvicorn.run(
        "rag_service.main:app",
        host="0.0.0.0",
        port=cfg.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
