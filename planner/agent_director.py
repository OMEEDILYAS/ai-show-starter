import argparse, json, os, requests
from pathlib import Path

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

SYS = """You are a short-form video director. Output tight, platform-ready copy.
Rules:
- Title <= 48 chars, punchy, no hashtags.
- Overlay: one sentence, <= 80 chars, plain text.
- Narration: ~90–120 words (~45s), simple sentences.
- Avoid emojis, hashtags, links. No scene directions.
- Stay on topic and series tone."""

USER_TMPL = """Series: {series}
Episode #: {epnum}
Seed title: {seed_title}
Theme/context: {theme}

Produce JSON with keys: title, overlay, narration."""

def call_openai(prompt: str):
    if not OPENAI_API_KEY:
        raise SystemExit("OPENAI_API_KEY not set")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()
    out_dir = Path(f"out/{args.series}")
    plan_path = sorted(out_dir.glob("ep_*/plan.json"))[-1]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    prompt = USER_TMPL.format(
        series=args.series,
        epnum=plan.get("episode", 1),
        seed_title=plan.get("title", "Daily topic"),
        theme=plan.get("theme", plan.get("series", args.series))
    )
    content = call_openai(prompt)
    data = json.loads(content)

    plan["ai_title"] = data.get("title", plan.get("title"))
    plan["ai_overlay"] = data.get("overlay", plan.get("overlay", "Quick lesson."))
    plan["ai_narration"] = data.get("narration", plan.get("narration", ""))

    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print("[agent] updated:", plan_path)

if __name__ == "__main__":
    main()
