import json
import os
import httpx
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from auth import get_forward_auth

app = FastAPI()
templates = Jinja2Templates(directory="templates")


async def generate_questions(topic: str) -> list:
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
        "Content-Type": "application/json",
    }

    prompt = (
        f'Erstelle genau 10 Multiple-Choice-Fragen zum Thema "{topic}". '
        "Antworte ausschließlich mit einem JSON-Objekt in folgendem Format "
        "(kein Markdown, kein Text davor oder danach):\n"
        '{"questions": [{"question": "Frage?", "options": ["A", "B", "C", "D"], "correct": 0}]}\n'
        'Die "correct"-Zahl ist der Index (0–3) der richtigen Antwort. Erstelle genau 10 Fragen.'
    )

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ai_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0,
        )
        data = response.json()

    content = data["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    return json.loads(content)["questions"]


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, auth: dict = Depends(get_forward_auth)):
    return templates.TemplateResponse(
        "index.html", {"request": request, "user_id": auth["user_id"]}
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    topic: str = Form(...),
    auth: dict = Depends(get_forward_auth),
):
    questions = await generate_questions(topic)
    return templates.TemplateResponse(
        "quiz.html",
        {
            "request": request,
            "user_id": auth["user_id"],
            "topic": topic,
            "questions": questions,
            "questions_json": json.dumps(questions, ensure_ascii=False),
        },
    )


@app.post("/submit", response_class=HTMLResponse)
async def submit(request: Request, auth: dict = Depends(get_forward_auth)):
    form = await request.form()
    questions = json.loads(form.get("questions_json"))
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
        "results.html",
        {
            "request": request,
            "user_id": auth["user_id"],
            "topic": topic,
            "results": results,
            "score": score,
            "total": len(questions),
        },
    )
