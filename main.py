import os
import json
import re
import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from auth import get_forward_auth

app = FastAPI()
template_env = Environment(loader=FileSystemLoader("templates"))


async def generate_questions(topic: str) -> list[dict]:
    ai_url = os.getenv("AI_SERVICE_URL")
    app_id = os.getenv("APP_ID")
    app_token = os.getenv("APP_TOKEN")
    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL")
    model = os.getenv("AI_MODEL", "gpt-4o")

    prompt = (
        f'Erstelle genau 5 Multiple-Choice-Fragen zum Thema "{topic}".\n'
        "Antworte NUR mit einem JSON-Array, ohne weitere Erklärungen oder Markdown.\n"
        "Format:\n"
        "[\n"
        '  {"question": "Frage?", "options": ["A", "B", "C", "D"], "correct": 0},\n'
        "  ...\n"
        "]\n"
        '"correct" ist der Index (0–3) der richtigen Antwort.'
    )

    headers = {
        "X-App-Id": app_id,
        "X-App-Token": app_token,
        "Authorization": f"Bearer {api_key}",
        "X-AI-Base-Url": base_url,
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            ai_url,
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]

    content = re.sub(r"```(?:json)?\s*", "", content).strip()
    content = re.sub(r"```\s*$", "", content).strip()
    return json.loads(content)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    auth = get_forward_auth(request)
    return template_env.get_template("index.html").render(user_id=auth["user_id"])


@app.post("/generate", response_class=HTMLResponse)
async def generate(request: Request, topic: str = Form(...)):
    auth = get_forward_auth(request)
    try:
        questions = await generate_questions(topic)
        return template_env.get_template("quiz.html").render(
            user_id=auth["user_id"],
            topic=topic,
            questions=questions,
            questions_json=json.dumps(questions, ensure_ascii=False),
        )
    except Exception as e:
        return template_env.get_template("index.html").render(
            user_id=auth["user_id"],
            error=f"Fehler beim Generieren der Fragen: {e}",
        )


@app.post("/results", response_class=HTMLResponse)
async def results(request: Request):
    auth = get_forward_auth(request)
    form = await request.form()
    topic = form.get("topic", "")
    questions = json.loads(form.get("questions_json", "[]"))

    score = 0
    results_data = []
    for i, q in enumerate(questions):
        raw = form.get(f"answer_{i}")
        user_idx = int(raw) if raw is not None else -1
        correct_idx = q["correct"]
        is_correct = user_idx == correct_idx
        if is_correct:
            score += 1
        results_data.append(
            {
                "question": q["question"],
                "options": q["options"],
                "correct": correct_idx,
                "user_answer": user_idx,
                "is_correct": is_correct,
            }
        )

    return template_env.get_template("results.html").render(
        user_id=auth["user_id"],
        topic=topic,
        score=score,
        total=len(questions),
        results=results_data,
    )
