# planner/agent_director.py
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import requests  # needed for API call

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

SYS = """You are a short-form video director. Output tight, platform-ready copy.
Rules:
- Title <= 48 chars, punchy, no hashtags.
- Overlay: one sentence, <= 80 chars, plain text.
- Narration: 110–140 words (target ~50–60 seconds), clear and simple.
- Avoid emojis, hashtags, links. No scene directions.
- Stay on topic and series tone.
- If a 'curriculum' is provided, STRICTLY base the content on it (summarize in your own words)."""

USER_TMPL = """Series: {series}
Episode #: {epnum}
Seed title: {seed_title}
Theme/context: {theme}
{maybe_curriculum}

Produce compact JSON with keys: title, overlay, narration."""

def call_openai(prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise SystemExit("OPENAI_API_KEY not set")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers=headers, json=body, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def ensure_plan(series: str) -> Path:
    out_dir = Path("out") / series
    plans = sorted(out_dir.glob("ep_*/plan.json"))
    if plans:
        return plans[-1]

    # No plan.json yet → call planner
    print(f"[agent] No plan.json found for {series}. Running planner…")
    res = subprocess.run(
        [sys.executable, "planner/plan_next.py", "--series", series],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise SystemExit(f"[agent] planner failed for {series} (exit {res.returncode})")

    plans = sorted(out_dir.glob("ep_*/plan.json"))
    if not plans:
        raise SystemExit(f"[agent] planner ran but still no plan.json in out/{series}/ep_*/")
    return plans[-1]

def load_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    plan_path = ensure_plan(args.series)
    plan = {}
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception:
        plan = {}

    # Resolve episode dir and assets
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    # Pull any staged curriculum (optional)
    curriculum_txt = assets / "curriculum.txt"
    curriculum = load_text(curriculum_txt)

    # Inputs to the director
    series = args.series
    epnum = plan.get("episode", 1)
    seed_title = plan.get("title", "Daily topic")
    theme = plan.get("theme", plan.get("series", series))

    maybe_curr = f"Curriculum (strict):\n{curriculum}\n" if curriculum else ""

    prompt = USER_TMPL.format(
        series=series,
        epnum=epnum,
        seed_title=seed_title,
        theme=theme,
        maybe_curriculum=maybe_curr,
    )

    # Call the model
    try:
        content = call_openai(prompt)
        data = json.loads(content)
    except Exception as e:
        # Fail-soft: keep previous values if model hiccups
        print(f"[agent] OpenAI/director failed, keeping prior fields. Error: {e}", file=sys.stderr)
        data = {}

    # Merge into plan
    plan["ai_title"] = data.get("title", plan.get("ai_title", plan.get("title")))
    plan["ai_overlay"] = data.get("overlay", plan.get("ai_overlay", plan.get("overlay", "Quick lesson.")))
    plan["ai_narration"] = data.get("narration", plan.get("ai_narration", plan.get("narration", "")))

    # Optional: include a hint for downstream steps
    plan["duration_target_sec"] = plan.get("duration_target_sec", 55)
    if curriculum:
        plan["curriculum_used"] = True

    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print("[agent] updated:", plan_path)

if __name__ == "__main__":
    main()