import os
import json
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from openai import AsyncOpenAI
from auth import get_forward_auth

app = FastAPI()

# Jinja2 Template Environment
template_env = Environment(loader=FileSystemLoader("templates"))

# Initialize AI Client
def get_ai_client():
    ai_url = os.getenv("AI_SERVICE_URL")
    # Falls die URL bereits den vollen Pfad enthält, kürzen wir sie für die OpenAI Library
    # Die Library hängt selbst /chat/completions an.
    if ai_url.endswith("/v1/chat/completions"):
        ai_url = ai_url.replace("/chat/completions", "")
    elif not ai_url.endswith("/v1"):
        # Falls /v1 fehlt (und es nicht der volle Pfad war), hängen wir es an
        ai_url = ai_url.rstrip("/") + "/v1"
    return AsyncOpenAI(
        base_url=ai_url,
        api_key=os.getenv("AI_API_KEY"),
        default_headers={
            "X-App-Id": os.getenv("APP_ID"),
            "X-App-Token": os.getenv("APP_TOKEN"),
            "X-AI-Base-Url": os.getenv("AI_BASE_URL")
        }
    )


async def generate_quiz_questions(topic: str) -> list[dict]:
    """Generate 10 multiple choice questions using AI"""
    client = get_ai_client()
    model = os.getenv("AI_MODEL", "gpt-4o")
    
    prompt = f"""Generate exactly 10 multiple choice questions about the topic: "{topic}"

For each question, provide:
1. The question text
2. Exactly 4 answer options (a, b, c, d)
3. The correct answer (a, b, c, or d)

Return the response as a JSON array with this structure:
[
  {{
    "id": 1,
    "question": "Question text?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct": "a"
  }},
  ...
]

Return ONLY the JSON array, no other text."""

    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = response.choices[0].message.content
    questions = json.loads(content)
    return questions


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page - topic input"""
    auth = get_forward_auth(request)
    user_id = auth.get("user_id", "Unknown")
    
    template = template_env.get_template("index.html")
    return template.render(user_id=user_id, page="home")


@app.post("/quiz", response_class=HTMLResponse)
async def start_quiz(request: Request, topic: str = Form(...)):
    """Generate quiz questions for given topic"""
    auth = get_forward_auth(request)
    user_id = auth.get("user_id", "Unknown")
    
    try:
        questions = await generate_quiz_questions(topic)
    except Exception as e:
        template = template_env.get_template("index.html")
        return template.render(
            user_id=user_id,
            page="home",
            error=f"Error generating questions: {str(e)}"
        )
    
    template = template_env.get_template("index.html")
    return template.render(
        user_id=user_id,
        page="quiz",
        topic=topic,
        questions=questions,
        questions_json=json.dumps(questions)
    )


@app.post("/results", response_class=HTMLResponse)
async def show_results(request: Request, answers: str = Form(...)):
    """Evaluate answers and show results"""
    auth = get_forward_auth(request)
    user_id = auth.get("user_id", "Unknown")
    
    try:
        answers_dict = json.loads(answers)
        questions = answers_dict.get("questions", [])
        user_answers = answers_dict.get("answers", {})
        topic = answers_dict.get("topic", "")
        
        correct_count = 0
        results = []
        
        for q in questions:
            q_id = str(q["id"])
            user_answer = user_answers.get(q_id, "")
            correct_answer = q["correct"]
            is_correct = user_answer.lower() == correct_answer.lower()
            
            if is_correct:
                correct_count += 1
            
            results.append({
                "id": q["id"],
                "question": q["question"],
                "options": q["options"],
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct
            })
        
        percentage = (correct_count / len(questions) * 100) if questions else 0
        
        template = template_env.get_template("index.html")
        return template.render(
            user_id=user_id,
            page="results",
            topic=topic,
            correct_count=correct_count,
            total_questions=len(questions),
            percentage=percentage,
            results=results
        )
    except Exception as e:
        template = template_env.get_template("index.html")
        return template.render(
            user_id=user_id,
            page="home",
            error=f"Error processing results: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
