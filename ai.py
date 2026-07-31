import os
from openai import OpenAI

from dotenv import load_dotenv

from storage import load_json
from storage import save_json

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or "missing-api-key",
    base_url=os.getenv("GROQ_API_URL"),
)

HISTORY_FILE = os.path.join("data", "history.json")
history = load_json(HISTORY_FILE)
if not isinstance(history, list):
    history = []

MARKDOWN_INSTRUCTIONS = (
    "Format the response in clean markdown. "
    "Use headings, bullet points, and short sections when helpful. "
    "If math appears, write formulas in LaTeX using $...$ for inline math and $$...$$ for block math. "
    "Do not wrap the entire response in a code block."
)


def add_to_history(action, prompt, response):
    history.append({
        "action": action,
        "prompt": prompt,
        "response": response,
    })
    save_json(HISTORY_FILE, history)


def summarize_text(text):
    prompt = (
        "Summarize this text into clear study notes. "
        f"{MARKDOWN_INSTRUCTIONS}\n\n"
        f"Text:\n{text}"
    )
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=1,
        max_completion_tokens=2048,
        top_p=1,
        reasoning_effort="medium",
        stream=False,
        stop=None,
    )
    result = response.choices[0].message.content
    add_to_history("summarize", prompt, result)
    return result


def answer_questions(text, question):
    prompt = (
        f"{MARKDOWN_INSTRUCTIONS}\n\n"
        f"Context:\n{text}\n\n"
        f"Question:\n{question}"
    )
    response = client.responses.create(
        input=prompt,
        model="openai/gpt-oss-20b",
    )
    result = response.output_text
    add_to_history("question", prompt, result)
    return result


def generate_quiz(text):
    prompt = (
        "Generate a quiz from this text. "
        "Use markdown with numbered questions and clearly separated answers. "
        f"{MARKDOWN_INSTRUCTIONS}\n\n"
        f"Text:\n{text}"
    )
    response = client.responses.create(
        input=prompt,
        model="openai/gpt-oss-20b",
    )
    result = response.output_text
    add_to_history("quiz", prompt, result)
    return result
