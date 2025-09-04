# generator/gen_visuals_code.py
"""
Generate per-beat visuals code using an LLM and write a clean, syntactically
valid Python file at: out/<series>/ep_XXX/assets/visuals_code.py

Hardening:
- Strips Markdown code fences, chatter, and leading BOMs.
- Validates with compile(); if invalid, falls back to a safe stub and raises.
- Keeps prompt minimal but includes narration & first few beats for context.

Env:
- OPENAI_API_KEY    (required)
- VIS_GEN_MODEL     (optional; defaults to "gpt-4o-mini")
Usage:
    python generator/gen_visuals_code.py --series math_of_ML
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import json
from pathlib import Path

# ---- constants ----
DEFAULT_MODEL = os.environ.get("VIS_GEN_MODEL", "gpt-4o-mini")

SAFE_STUB = """\
# Auto-generated fallback visuals script (safe stub).
# If you see this, LLM code generation failed or returned invalid Python.
# We keep this valid so the pipeline can proceed without syntax errors.

def main():
    # Minimal no-op; renderer may overlay background/other layers.
    print("[visuals_stub] Running safe stub; no dynamic visuals generated.")

if __name__ == "__main__":
    main()
"""

PROMPT_TEMPLATE = """You are generating plain Python code (no Markdown fences) for a short educational vertical video.
Requirements:
- Output MUST be ONLY valid Python code. NO backticks, NO Markdown, NO prose.
- Prefer simple, dependency-light code. If you need a 3D scene, use vpython (if trivial) or basic math to compute 2D keyframes.
- The code will be executed by another tool; do NOT write files or call ffmpeg yourself unless clearly necessary.
- Keep side effects minimal. Print progress logs if helpful.

Context:
- Series: {series}
- Narration (excerpt): {narration_excerpt}
- Beat list (first few): {beats_excerpt}

Goals:
- Animate vectors, matrices, or simple diagrams matching the narration tone (math/MAS).
- Use simple loops/timesteps to represent progression.
- Provide a `main()` entrypoint; guard with `if __name__ == "__main__": main()`.

Return ONLY Python code. Again: NO markdown fences, NO commentary.
"""

# ---- helpers ----

def _fail(msg: str) -> None:
    print(f"[gen_visuals_code] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)

def find_latest_episode_dir(series: str) -> Path:
    root = Path("out") / series
    eps = sorted([p for p in root.glob("ep_*") if p.is_dir()])
    if not eps:
        _fail(f"No episode folders under {root}. Run planner first.")
    return eps[-1]

def read_text_safe(p: Path) -> str:
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return p.read_text(errors="ignore")

def sanitize_llm_to_code(text: str) -> str:
    """
    Strip markdown fences and chatter, return only Python code.
    """
    s = text.strip().lstrip("\ufeff")  # strip BOM if present

    # If fences present, extract the first fenced python block
    fence_pat = re.compile(
        r"```(?:python|py)?\s*(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    m = fence_pat.search(s)
    if m:
        s = m.group(1).strip()

    # If still contains stray triple backticks, drop them.
    s = s.replace("```python", "").replace("```py", "").replace("```", "").strip()

    # Sometimes models prepend "Here is the code:" lines.
    s = re.sub(r"^\s*(Here is|Here’s|Here are)[^\n]*\n", "", s, flags=re.IGNORECASE)

    return s

def validate_python(code: str) -> None:
    try:
        compile(code, "visuals_code.py", "exec")
    except SyntaxError as e:
        # Re-raise with cleaner message
        raise SyntaxError(f"Line {e.lineno}: {e.msg}") from None

# ---- LLM call ----

def call_openai_for_code(prompt: str, model: str) -> str:
    # Requires openai>=1.0
    try:
        from openai import OpenAI
    except Exception as e:
        _fail(f"openai package missing or incompatible: {e}")

    client = OpenAI()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You output only valid Python code. No Markdown, no explanations."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1200,
        )
    except Exception as e:
        _fail(f"OpenAI call failed: {e}")

    text = resp.choices[0].message.content or ""
    return text

# ---- main ----

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    ep_dir = find_latest_episode_dir(args.series)
    assets = ep_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    # Inputs
    narration = read_text_safe(assets / "narration.txt").strip()
    shotlist_path = assets / "shotlist.json"
    beats_excerpt = ""
    if shotlist_path.exists():
        try:
            beats = json.loads(shotlist_path.read_text(encoding="utf-8"))
            # Keep it short in the prompt
            beats_excerpt = json.dumps(beats[:4], ensure_ascii=False)
        except Exception:
            beats_excerpt = "[]"

    narration_excerpt = (narration[:600] + "…") if len(narration) > 600 else narration

    prompt = PROMPT_TEMPLATE.format(
        series=args.series,
        narration_excerpt=narration_excerpt or "(empty)",
        beats_excerpt=beats_excerpt or "[]",
    )

    # Call LLM for code
    model = DEFAULT_MODEL
    raw = call_openai_for_code(prompt, model)
    code = sanitize_llm_to_code(raw)

    # If model returned empty after sanitization, use stub
    if not code or not code.strip():
        code = SAFE_STUB
        (assets / "visuals_code_error.txt").write_text(
            "LLM returned empty output; wrote safe stub instead.\n", encoding="utf-8"
        )

    # Validate syntax; if bad, write stub but also keep the original for debugging
    try:
        validate_python(code)
        final_code = code
    except SyntaxError as e:
        # Save the bad code for inspection
        (assets / "visuals_code_raw.py").write_text(code, encoding="utf-8")
        # Switch to stub so downstream doesn't crash
        final_code = SAFE_STUB
        (assets / "visuals_code_error.txt").write_text(
            f"Invalid Python from LLM: {e}\nUsing safe stub instead.\n", encoding="utf-8"
        )

    # Always write the executable code to visuals_code.py
    out_py = assets / "visuals_code.py"
    out_py.write_text(final_code, encoding="utf-8")
    print(f"[gen_visuals_code] wrote {out_py.relative_to(Path.cwd())}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
