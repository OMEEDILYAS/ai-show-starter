#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_director.py
Purpose:
  - Reads the episode plan (plan.json) created by plan_next.py
  - Reads the source chunk (assets/source.txt)
  - Produces a strict 70–90s narration (≈150–190 words) that summarizes ONLY the source
  - Writes assets/narration.txt and assets/overlay.txt / assets/title.txt if missing

Why:
  - Prevents "psyche" or off-topic narration in MIXED channel by forcing the model
    to summarize ONLY the textbook chunk. No free-styling.

Env:
  - OPENAI_API_KEY (required)
  - OPENAI_MODEL (default: gpt-4o)

Notes:
  - We enforce "STRICT_SUMMARY". If the model strays, we regenerate once with an even harder constraint.
"""
import os, json, sys, time
from pathlib import Path

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

ROOT = Path(__file__).resolve().parents[1]

def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""

def _write_text(p: Path, s: str) -> None:
    p.write_text(s.strip() + "\n", encoding="utf-8")

def _load_json(p: Path) -> dict:
    return json.loads(_read_text(p)) if p.exists() else {}

def _save_json(p: Path, d: dict):
    p.write_text(json.dumps(d, indent=2), encoding="utf-8")

def _openai_chat(messages):
    # lightweight OpenAI call (avoid extra deps)
    import requests
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[director] ERROR: OPENAI_API_KEY missing", file=sys.stderr)
        sys.exit(1)
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 600,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def main():
    # Locate latest plan.json
    plans = sorted((ROOT / "out").rglob("ep_*/plan.json"))
    if not plans:
        print("[director] No plan.json found.", file=sys.stderr)
        sys.exit(1)
    plan_path = plans[-1]
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"

    plan = _load_json(plan_path)
    source = _read_text(assets / "source.txt")
    if not source.strip():
        print("[director] ERROR: source.txt empty or missing.", file=sys.stderr)
        sys.exit(1)

    # Title/overlay placeholders (could be refined by model but not required)
    title_path = assets / "title.txt"
    overlay_path = assets / "overlay.txt"
    if not title_path.exists():
        _write_text(title_path, f"{plan.get('effective_series','series')} — Chapter {plan.get('chapter','?')}")
    if not overlay_path.exists():
        _write_text(overlay_path, f"Section: {plan.get('section','?')}")

    sys_msg = {
        "role": "system",
        "content": (
            "You are a precise educator. You will receive an excerpt from a textbook.\n"
            "RULES:\n"
            "1) Produce a clear, engaging VO script of ~150–190 words (~70–90 seconds at slow pace).\n"
            "2) STRICT_SUMMARY: Use ONLY information from the excerpt. Do not invent, generalize, or shift topics.\n"
            "3) If equations/terms appear, you may name them (e.g., inner product, basis, payoff matrix), but no off-topic advice.\n"
            "4) Tone: calm, concise teacher. No hype. No commands to the audience.\n"
            "5) No lists unless needed; prefer short paragraphs with smooth transitions.\n"
        )
    }
    user_msg = {
        "role": "user",
        "content": (
            "Source excerpt:\n"
            f"<<<\n{source}\n>>>\n\n"
            "Write the narration now. 150–190 words. STRICT_SUMMARY."
        )
    }

    text = _openai_chat([sys_msg, user_msg]).strip()

    # Simple guard: if the model goes off-topic (keywords like 'stress', 'habits' but not present in source),
    # call again with even stronger instruction.
    lower = text.lower()
    suspicious = any(k in lower for k in ["stress", "habit", "success", "calm"]) and not any(
        k in source.lower() for k in ["stress", "habit", "success", "calm"]
    )
    if suspicious:
        print("[director] off-topic detected → retry with stricter instruction")
        sys_msg["content"] += "\n6) If any part of your output is not directly supported by the excerpt, REPLACE it with a sentence that is."
        text = _openai_chat([sys_msg, user_msg]).strip()

    _write_text(assets / "narration.txt", text)
    print("[director] narration written:", len(text.split()), "words")
    # persist back any minor meta we might want later
    plan["narration_words"] = len(text.split())
    _save_json(plan_path, plan)

if __name__ == "__main__":
    main()
