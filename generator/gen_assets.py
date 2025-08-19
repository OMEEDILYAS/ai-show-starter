# generator/gen_assets.py
import argparse
import json
import os
from pathlib import Path
import textwrap

from tts_openai import synthesize

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def load_plan(series: str) -> tuple[dict, Path]:
    out_dir = Path("out") / series
    # Pick most recent episode plan.json
    plan_paths = sorted(out_dir.glob("ep_*/plan.json"))
    if not plan_paths:
        raise SystemExit(f"No plan.json found in out/{series}/ep_*/")
    plan_path = plan_paths[-1]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    return plan, plan_path

def write_text(path: Path, content: str):
    path.write_text(content, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    series = args.series
    plan, plan_path = load_plan(series)

    # Prefer AI-enriched fields if present (from agent_director), fallback to seed fields
    title = plan.get("ai_title") or plan.get("title") or f"{series} daily"
    overlay = plan.get("ai_overlay") or plan.get("overlay") or "Learn something new!"
    narration = plan.get("ai_narration") or plan.get("narration") or plan.get("script") or "Welcome to today’s episode."

    # Normalize narration length for ≈45s (light touch)
    narration = " ".join(narration.split())
    narration = textwrap.shorten(narration, width=1200, placeholder="…")

    ep_dir = Path(plan_path).parent
    assets_dir = ep_dir / "assets"
    ensure_dir(assets_dir)

    # Save text assets for downstream steps
    write_text(assets_dir / "title.txt", title)
    write_text(assets_dir / "overlay.txt", overlay)
    write_text(assets_dir / "narration.txt", narration)

    # Generate voice-over with OpenAI TTS → voice.wav
    voice_path = assets_dir / "voice.wav"
    print(f"[TTS] Synthesizing VO to {voice_path} …")
    synthesize(narration, str(voice_path))
    print("[TTS] Done.")

    # (Optional) placeholder background music selection can be added later
    # For now, assembly/build_video.py should detect and mix voice.wav if present.

    # Update plan with resolved fields so downstream sees consistent values
    plan["resolved_title"] = title
    plan["resolved_overlay"] = overlay
    plan["resolved_narration"] = narration
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"[gen_assets] Wrote assets in {assets_dir}")

if __name__ == "__main__":
    main()
