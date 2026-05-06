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
