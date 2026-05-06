import os
import json
import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from auth import get_forward_auth

app = FastAPI()
template_env = Environment(loader=FileSystemLoader("templates"))


async def generate_questions(topic: str) -> list:
    ai_url = os.getenv("AI_SERVICE_URL")
    app_id = os.getenv("APP_ID")
    app_token = os.getenv("APP_TOKEN")
    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL")
    model = os.getenv("AI_MODEL", "gpt-4o")

    prompt = (
        f'Erstelle 5 Multiple-Choice-Fragen zum Thema "{topic}". '
        "Antworte NUR mit einem JSON-Array ohne Markdown-Formatierung, in exakt diesem Format:\n"
        '[\n'
        '  {\n'
        '    "question": "Frage hier?",\n'
        '    "options": ["Option A", "Option B", "Option C", "Option D"],\n'
        '    "correct": 0\n'
        '  }\n'
        ']\n'
        '"correct" ist der 0-basierte Index (0–3) der richtigen Antwort. '
        "Nur ein JSON-Array, kein weiterer Text."
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
        response = await client.post(ai_url, json=payload, headers=headers, timeout=60.0)
        data = response.json()

    content = data["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return json.loads(content.strip())


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    auth = get_forward_auth(request)
    return template_env.get_template("index.html").render(user_id=auth["user_id"])


@app.post("/generate", response_class=HTMLResponse)
async def generate(request: Request, topic: str = Form(...)):
    auth = get_forward_auth(request)
    questions = await generate_questions(topic)
    questions_json = json.dumps(questions, ensure_ascii=False)
    return template_env.get_template("quiz.html").render(
        user_id=auth["user_id"],
        topic=topic,
        questions=questions,
        questions_json=questions_json,
    )


@app.post("/results", response_class=HTMLResponse)
async def results(request: Request):
    auth = get_forward_auth(request)
    form = await request.form()

    questions = json.loads(form.get("questions_json", "[]"))
    topic = form.get("topic", "")

    answers = []
    for i in range(len(questions)):
        raw = form.get(f"answer_{i}")
        answers.append(int(raw) if raw is not None else -1)

    score = sum(1 for i, q in enumerate(questions) if answers[i] == q["correct"])

    results_data = [
        {
            "question": q["question"],
            "options": q["options"],
            "correct": q["correct"],
            "selected": answers[i],
            "is_correct": answers[i] == q["correct"],
        }
        for i, q in enumerate(questions)
    ]

    return template_env.get_template("results.html").render(
        user_id=auth["user_id"],
        topic=topic,
        score=score,
        total=len(questions),
        results=results_data,
    )
