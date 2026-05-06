import json
import os
import sys
import traceback

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from openai import AsyncOpenAI

from auth import get_forward_auth

app = FastAPI()
templates = Jinja2Templates(directory="templates")


def get_ai_client() -> AsyncOpenAI:
    ai_url = os.getenv("AI_SERVICE_URL", "")
    if ai_url.endswith("/v1/chat/completions"):
        ai_url = ai_url.replace("/chat/completions", "")
    elif not ai_url.endswith("/v1"):
        ai_url = ai_url.rstrip("/") + "/v1"

    return AsyncOpenAI(
        base_url=ai_url,
        api_key=os.getenv("AI_API_KEY"),
        default_headers={
            "X-App-Id": os.getenv("APP_ID"),
            "X-App-Token": os.getenv("APP_TOKEN"),
            "X-AI-Base-Url": os.getenv("AI_BASE_URL"),
        },
    )


async def generate_questions(topic: str) -> list[dict]:
    client = get_ai_client()
    model = os.getenv("AI_MODEL", "gpt-4o")

    prompt = (
        f'Erstelle genau 10 Multiple-Choice-Fragen zum Thema "{topic}". '
        "Antworte ausschließlich mit einem JSON-Array in folgendem Format "
        "(kein Markdown, kein Text davor oder danach):\n"
        '[{"question": "Frage?", "options": ["A", "B", "C", "D"], "correct": 0}]\n'
        'Die "correct"-Zahl ist der Index (0–3) der richtigen Antwort. Erstelle genau 10 Fragen auf Deutsch.'
    )

    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    parsed = json.loads(content)
    if isinstance(parsed, dict) and "questions" in parsed:
        return parsed["questions"]
    return parsed


def safe_user_id(request: Request) -> str:
    try:
        return get_forward_auth(request).get("user_id") or "Gast"
    except Exception:
        return "Gast"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user_id = safe_user_id(request)
    return templates.TemplateResponse(
        request, "index.html", {"user_id": user_id, "error": None}
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(request: Request, topic: str = Form(...)):
    user_id = safe_user_id(request)
    try:
        questions = await generate_questions(topic)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "user_id": user_id,
                "error": f"Fehler beim Generieren der Fragen: {e}",
            },
        )

    return templates.TemplateResponse(
        request,
        "quiz.html",
        {
            "user_id": user_id,
            "topic": topic,
            "questions": questions,
            "questions_json": json.dumps(questions, ensure_ascii=False),
        },
    )


@app.post("/submit", response_class=HTMLResponse)
async def submit(request: Request):
    user_id = safe_user_id(request)
    form = await request.form()
    try:
        questions = json.loads(form.get("questions_json", "[]"))
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return templates.TemplateResponse(
            request,
            "index.html",
            {"user_id": user_id, "error": f"Auswertung fehlgeschlagen: {e}"},
        )

    topic = form.get("topic", "")
    results = []
    score = 0
    for i, q in enumerate(questions):
        raw = form.get(f"answer_{i}")
        selected = int(raw) if raw is not None else -1
        is_correct = selected == q["correct"]
        if is_correct:
            score += 1
        results.append(
            {
                "question": q["question"],
                "options": q["options"],
                "selected": selected,
                "correct": q["correct"],
                "is_correct": is_correct,
            }
        )

    return templates.TemplateResponse(
        request,
        "results.html",
        {
            "user_id": user_id,
            "topic": topic,
            "results": results,
            "score": score,
            "total": len(questions),
        },
    )
