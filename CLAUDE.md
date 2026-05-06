# Project Overview

FastAPI app with Jinja2 HTML templates, deployed via Docker on the lumentic.de hub infrastructure with forward-auth and an AI proxy.

## Tech Stack

- **Backend:** FastAPI (Python)
- **Frontend:** HTML with Jinja2 templates; inline CSS (keep modern, user-ID top-right)
- **Package manager:** uv — always maintain `pyproject.toml` and `uv.lock`

## Required Files

- `main.py` — app logic
- `auth.py` — identity extraction (see below)
- `templates/index.html` — UI with CSS placing user-ID top-right
- `pyproject.toml` — dependencies: `fastapi`, `uvicorn`, `jinja2`, `python-multipart`
- `uv.lock`
- `Dockerfile`
- `docker-compose.yaml` (must end in `.yaml`, not `.yml`)

## Templates — Jinja2

Two equivalent options. Pick one and use it consistently:

**Option A — raw Jinja2 (recommended, version-stable):**

```python
from jinja2 import Environment, FileSystemLoader
template_env = Environment(loader=FileSystemLoader("templates"))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return template_env.get_template("index.html").render(user_id="...")
```

**Option B — FastAPI's `Jinja2Templates`:**

If you use this, you MUST use the new signature `TemplateResponse(request, name, context)`. The old positional form `TemplateResponse(name, context)` is **broken** in Starlette ≥ 0.29 — the dict is interpreted as the template name, causing `TypeError: unhashable type: 'dict'` inside the template cache.

```python
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"user_id": "..."})
```

Do not put `"request": request` inside the context dict — pass `request` as the first positional argument.

## Auth (`auth.py`) — use exactly as written

```python
from __future__ import annotations
from fastapi import HTTPException, Request

def get_forward_auth(request: Request) -> dict[str, str]:
    email_hash = request.headers.get("x-auth-email-hash")
    session_id = request.headers.get("x-auth-session-id")
    user_id = request.headers.get("x-auth-user-id", "")

    if not email_hash or not session_id:
        raise HTTPException(status_code=500, detail="auth_headers_missing")

    return {"email_hash": email_hash, "session_id": session_id, "user_id": user_id}
```

## Dockerfile Template

Verify it fits the app before using; adjust only if needed.

```dockerfile
FROM ghcr.io/astral-sh/uv:latest AS uv_setup
FROM python:3.13-slim AS runtime

COPY --from=uv_setup /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

RUN useradd -r -u 10001 appuser
RUN mkdir -p /app && chown appuser /app

COPY . .

RUN uv sync --no-dev --no-install-project

ENV PATH="/app/.venv/bin:$PATH"
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
```

## docker-compose.yaml Template

- `SERVICE_NAME` is defined by the user in the current chat session — substitute it everywhere `APP_NAME` appears (including the `SUBDOMAIN` placeholder).
- Subdomain: `SERVICE_NAME.hub.lumentic.de`
- All router labels MUST use the same router name (`APP_NAME`). Do not add suffixes like `-test` to any of them — Traefik would otherwise create multiple half-configured routers and the app becomes unreachable.
- AI proxy environment variables (`AI_SERVICE_URL`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`, `AUTH_UPSTREAM`) must be declared explicitly so the container actually receives them — Coolify only injects them into the host environment, not into the container.
- Use .yaml as a file ending and not .yml, this is really important.

```yaml
version: '3.8'
services:
  APP_NAME:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - APP_ID=${APP_ID}
      - APP_TOKEN=${APP_TOKEN}
      - AI_SERVICE_URL=${AI_SERVICE_URL}
      - AI_BASE_URL=${AI_BASE_URL}
      - AI_API_KEY=${AI_API_KEY}
      - AI_MODEL=${AI_MODEL}
      - AUTH_UPSTREAM=${AUTH_UPSTREAM}
    networks:
      - coolify
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=coolify"
      - "traefik.http.routers.APP_NAME.rule=Host(`APP_NAME.hub.lumentic.de`)"
      - "traefik.http.routers.APP_NAME.tls.certresolver=letsencrypt"
      - "traefik.http.routers.APP_NAME.entrypoints=https"
      - "traefik.http.routers.APP_NAME.middlewares=forward-auth@file"
      - "traefik.http.routers.APP_NAME.service=APP_NAME"
      - "traefik.http.services.APP_NAME.loadbalancer.server.port=5000"

networks:
  coolify:
    external: true
```

## AI Proxy

### Environment Variables

| Variable | Purpose |
|---|---|
| `APP_ID` | App identifier |
| `APP_TOKEN` | App authentication token |
| `AI_SERVICE_URL` | Full endpoint URL including path, e.g. `http://ai-service:5000/v1/chat/completions` — use directly, do NOT append `/v1/chat/completions` again |
| `AI_API_KEY` | API key forwarded to provider |
| `AI_BASE_URL` | Provider base URL forwarded via header |
| `AI_MODEL` | Model name (e.g. `gpt-4o`) |
| `AUTH_UPSTREAM` | Upstream auth service |
| `AI_PROVIDER` | AI provider identifier |

### httpx (direct)

```python
import os
import httpx

async def get_ai_response(prompt: str):
    ai_url = os.getenv("AI_SERVICE_URL")
    app_id = os.getenv("APP_ID")
    app_token = os.getenv("APP_TOKEN")
    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL")
    model = os.getenv("AI_MODEL", "gpt-4o")

    headers = {
        "X-App-Id": app_id,
        "X-App-Token": app_token,
        "Authorization": f"Bearer {api_key}",
        "X-AI-Base-Url": base_url,
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            ai_url,  # AI_SERVICE_URL already contains the full path
            json=payload,
            headers=headers,
            timeout=30.0
        )
        return response.json()
```

### OpenAI SDK

```python
import os
from openai import AsyncOpenAI

async def get_ai_response_sdk(prompt: str):
    ai_url = os.getenv("AI_SERVICE_URL")
    app_id = os.getenv("APP_ID")
    app_token = os.getenv("APP_TOKEN")
    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL")
    model = os.getenv("AI_MODEL", "gpt-4o")

    sdk_base_url = ai_url.replace("/chat/completions", "").rstrip("/")
    if not sdk_base_url.endswith("/v1"):
        sdk_base_url += "/v1"

    client = AsyncOpenAI(
        base_url=sdk_base_url,
        api_key=api_key,
        default_headers={
            "X-App-Id": app_id,
            "X-App-Token": app_token,
            "X-AI-Base-Url": base_url
        }
    )

    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content
```
