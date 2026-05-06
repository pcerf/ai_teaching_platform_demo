# Prompt für KI-Agent

Erstelle eine vollständige Python-Webanwendung basierend auf den folgenden Anforderungen. Die Anwendung soll **AI Multiple Choice** heißen.

---

## 0. Einstellungen

- **Name unter der die App erreichbar ist (ohne Leerzeiche und Sonderzeichen):**
  SERVICE_NAME: ki-quiz-test2

---

## 1. Funktionale Anforderungen

- **Zweck:**  
  Ein Multiple-Choice-Test. Der Nutzer erhält zunächst ein Textfeld, in das er ein Thema eingeben kann. Dieses wird an eine KI übermittelt, die daraufhin genau 10 Fragen generiert.

- **Ablauf:**  
  Der Nutzer sieht die Fragen, wählt Antworten aus und erhält nach dem Absenden eine Auswertung (Wie viele Fragen richtig/falsch beantwortet wurden).

- **UI:**  
  Zeige oben rechts in der Ecke permanent die `user_id` des angemeldeten Benutzers an.

---

## 2. Technischer Stack

- **Backend:** FastAPI (Python)  
- **Frontend:** HTML mit Jinja2-Templates  
- Nutze einfaches CSS innerhalb der Templates, um das Design modern zu gestalten und die User-ID korrekt oben rechts zu positionieren.
- **Paketverwaltung:** uv  
- Erstelle eine passende `pyproject.toml` und `uv.lock`

---

## 3. Code-Vorgaben (Strikt einzuhalten)

### A) Authentifizierung (`auth.py`)

Verwende exakt diesen Code für die Identitätsextraktion:

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


### B) Docker-Konfiguration (Dockerfile)
- Verwende dieses Template und prüfe, ob es zu unserer App passt oder ob noch Anpassungen notwendig sind.

 ```
FROM ghcr.io/astral-sh/uv:latest AS uv_setup
FROM python:3.13-slim AS runtime

COPY --from=uv_setup /uv /uvx /bin/

# UV Konfiguration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

RUN useradd -r -u 10001 appuser
RUN mkdir -p /app && chown appuser /app

# Alle Projektdateien kopieren (damit auch uv.lock da ist)
COPY . .

# Installation der Abhängigkeiten
# --no-install-project ist wichtig, da wir die App nur ausführen, nicht als Paket installieren wollen
RUN uv sync --no-dev --no-install-project

ENV PATH="/app/.venv/bin:$PATH"
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
 ```
 
 ### C) Deployment (docker-compose.yaml)
 - Unter 0. ganz oben wurde die Variable SERVICE_NAME definiert
 - Verwende dieses Template und setze den Service-Namen auf SERVICE_NAME
 - Die Subdomain soll SERVICE_NAME.hub.lumentic.de lauten.
 - Überall wo APP_NAME steht kannst du den Inhalt der Variablen SERVICE_NAME einsetzen
 - Du musst keine weiteren Environments setzen, sie werden automatisch gesetzt.
 - Die Docker-Compose muss auf .yaml enden. Das ist sehr wichtig.
 - Überprüfe, ob alles richtig ist.

 
 ```
 version: '3.8'
 services:
   APP_NAME:
     build:
       context: .
       dockerfile: Dockerfile
     environment:
       - APP_ID=${APP_ID}
       - APP_TOKEN=${APP_TOKEN}
     networks:
       - coolify
     labels:
       - "traefik.enable=true"
       - "traefik.docker.network=coolify"
       - "traefik.http.routers.APP_NAME-test.rule=Host(`SUBDOMAIN.hub.lumentic.de`)"
       - "traefik.http.routers.APP_NAME.tls.certresolver=letsencrypt"
       - "traefik.http.routers.APP_NAME.entrypoints=https"
       - "traefik.http.routers.APP_NAME.middlewares=forward-auth@file"
       - "traefik.http.routers.APP_NAME.service=ki-quiz-test"
       - "traefik.http.services.APP_NAME.loadbalancer.server.port=5000"
 
 networks:
   coolify:
     external: true
 
 ```
 
 ### D) AI-Proxy
 
 - Die folgenden Umgebungsvariablen stehen dir zur Verfügung:
 - APP_ID
 - APP_TOKEN
 - AI_SERVICE_URL
 - AUTH_UPSTREAM
 - AI_PROVIDE
 - AI_API_KEY
 - AI_MODEL
 - AI_BASE_URL
 
 ```
 
 # --- TUTORIAL für den AI-Proxy ----
# Hier ist ein Python-Beispielcode, der zeigt, wie man mit unserem AI-Proxy kommuniziert.
# Einmal mit der OpenAI Library und einmal direkt mit Httpx.


import os
import httpx

async def get_ai_response(prompt: str):
    # 1. Variablen aus der Umgebung laden
    ai_url = os.getenv("AI_SERVICE_URL")
    app_id = os.getenv("APP_ID")
    app_token = os.getenv("APP_TOKEN")
    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL")
    model = os.getenv("AI_MODEL", "gpt-4o")

    # 2. Header vorbereiten
    headers = {
        "X-App-Id": app_id,
        "X-App-Token": app_token,
        "Authorization": f"Bearer {api_key}",
        "X-AI-Base-Url": base_url,
        "Content-Type": "application/json"
    }

    # 3. Payload (OpenAI-kompatibel)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }

    # 4. Anfrage an den Proxy senden
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ai_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30.0
        )
        return response.json()
        
```

### OpenAI Lib

```
import os
from openai import AsyncOpenAI

async def get_ai_response_sdk(prompt: str):
    # 1. Variablen aus der Umgebung laden
    ai_url = os.getenv("AI_SERVICE_URL")  # z.B. http://ai-service:5000/v1
    app_id = os.getenv("APP_ID")
    app_token = os.getenv("APP_TOKEN")
    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL")
    model = os.getenv("AI_MODEL", "gpt-4o")

    # 2. base_url für das SDK vorbereiten
    # Das SDK erwartet den Pfad bis /v1. Wir stellen sicher, dass nichts doppelt ist.
    sdk_base_url = ai_url.replace("/chat/completions", "").rstrip("/")
    if not sdk_base_url.endswith("/v1"):
        sdk_base_url += "/v1"

    # 3. Client initialisieren
    client = AsyncOpenAI(
        base_url=sdk_base_url,
        api_key=api_key,
        default_headers={
            "X-App-Id": app_id,
            "X-App-Token": app_token,
            "X-AI-Base-Url": base_url
        }
    )

    # 4. Anfrage wie gewohnt ausführen
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


 ```
 
 
 ## 4. Ausgabe
 
 - Bitte generiere den vollständigen Code für:
 - main.py (inklusive der 10 Fragen und der Logik)
 - auth.py (wie oben vorgegeben)
 - Benutze den AI-Proxy
 - templates/index.html (mit CSS für die User-ID oben rechts)
 - pyproject.toml (mit Abhängigkeiten: fastapi, uvicorn, jinja2, python-multipart)
 - uv.lock
