#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_shotlist.py
Purpose:
  - Use the same source excerpt + narration to propose 12–18 beats (cards)
  - Each beat gets 4–6s, distinct visual intent, and short on-screen text
  - Enforce uniqueness: avoid repeating same idea/keywords/visual mode
  - For MIXED series, we route by plan["effective_series"] so visuals & narration match

Env:
  - OPENAI_API_KEY (required)
  - OPENAI_MODEL (default: gpt-4o)

Outputs:
  - assets/shotlist.json with a list of beats:
      [{"title": "...", "text": "...", "keywords": ["vectors","projection"], "duration": 5.2}, ...]
"""
import os, json, sys, random
from pathlib import Path

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
ROOT = Path(__file__).resolve().parents[1]

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""

def _write(p: Path, s: str):
    p.write_text(s, encoding="utf-8")

def _openai_chat(messages):
    import requests
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[shotlist] ERROR: OPENAI_API_KEY missing", file=sys.stderr)
        sys.exit(1)
    url = "https://api.openai.com/v1/chat/completions"
    payload = {"model": OPENAI_MODEL, "messages": messages, "temperature": 0.8, "max_tokens": 1200}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def main():
    plans = sorted((ROOT / "out").rglob("ep_*/plan.json"))
    if not plans:
        print("[shotlist] No plan.json found", file=sys.stderr)
        sys.exit(1)
    plan_path = plans[-1]
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"
    plan = json.loads(_read(plan_path))
    source = _read(assets / "source.txt")
    narration = _read(assets / "narration.txt")

    if not source.strip() or not narration.strip():
        print("[shotlist] ERROR: missing source or narration", file=sys.stderr)
        sys.exit(1)

    # For mixed: use effective_series to pick the right visual domain words
    series = plan.get("effective_series", plan.get("series", "math_of_ML"))

    if series in ("math_of_ML", "ai_teacher", "ai_teacher_linear_algebra"):
        domain_hint = (
            "This is LINEAR ALGEBRA. Favor visuals like: vectors, projections, rotations, basis change, "
            "grid deformations under 2x2 matrices, determinant/area, eigenvectors."
        )
    elif series in ("MAS", "ai_teacher_mas"):
        domain_hint = (
            "This is MULTI-AGENT SYSTEMS. Favor visuals like: small agent graphs (ring/star/grid), "
            "message passing pulses, payoff matrices (2x2), simple gridworld traces."
        )
    else:
        # In case future series appear; default to neutral diagrams
        domain_hint = "Favor neutral math/graph diagrams (no lifestyle/psych content)."

    sys_msg = {
        "role": "system",
        "content": (
            "You create concise visual beats for a vertical video. "
            "RULES:\n"
            "1) Output 12–18 beats, 4–6 seconds each.\n"
            "2) STRICT_SUMMARY: Align with the excerpt and narration ONLY. No lifestyle/psych advice.\n"
            "3) Uniqueness: Each beat must have distinct on-screen text and keywords. Avoid repeating visuals.\n"
            "4) On-screen text: ≤ 12 words; short phrases; no punctuation unless needed.\n"
            "5) Keywords: 2–4 words that map to a visual mode (e.g., vectors, projection, ring graph, payoff).\n"
            "6) Never reference the audience (no 'you').\n"
        )
    }
    user_msg = {
        "role": "user",
        "content": (
            f"{domain_hint}\n\n"
            "Source excerpt:\n"
            f"<<<\n{source}\n>>>\n\n"
            "Narration (for context):\n"
            f"<<<\n{narration}\n>>>\n\n"
            "Return JSON only with this shape:\n"
            '[{"title":"...","text":"...","keywords":["k1","k2"],"duration":5.2}, ...]\n'
        )
    }
    import json as pyjson
    raw = _openai_chat([sys_msg, user_msg])

    # Try to parse; if it fails, fall back to a simple static list
    try:
        beats = pyjson.loads(raw)
        if not isinstance(beats, list):
            raise ValueError("not a list")
    except Exception as e:
        print("[shotlist] WARN: parse failed, using fallback:", e)
        beats = [
            {"title": "Idea", "text": "Core idea", "keywords": ["diagram"], "duration": 5.0}
            for _ in range(12)
        ]

    # Enforce: 12–18, 4–6s, unique-ish keywords
    # Trim or pad
    if len(beats) < 12:
        beats += beats[: 12 - len(beats)]
    if len(beats) > 18:
        beats = beats[:18]

    # Durations
    for b in beats:
        d = float(b.get("duration", 5.0))
        b["duration"] = min(6.0, max(4.0, d))

    # Uniqueness: drop exact-duplicate keyword sets by re-rolling titles slightly
    seen = set()
    uniq = []
    for b in beats:
        kws = tuple(sorted((b.get("keywords") or [])[:4]))
        if kws in seen:
            # perturb text minimally
            t = (b.get("text") or "Beat").strip()
            b["text"] = t if len(t) < 11 else t[:10]
        else:
            seen.add(kws)
        uniq.append(b)
    beats = uniq

    # Save
    out_path = assets / "shotlist.json"
    _write(out_path, json.dumps(beats, indent=2))
    print(f"[shotlist] beats={len(beats)} → {out_path}")

if __name__ == "__main__":
    main()
