import json, argparse
from pathlib import Path

SCRIPT_TMPL = """Title: {title}
Hook: Today in {series}, {title}.
Body: {body}
CTA: Follow for tomorrow's episode.
"""

def synthesize_script(plan):
    title = plan["title"] or "A quick lesson"
    if plan["series"] == "ai_teacher":
        body = "Explain the concept with one concrete visual example and one short tip."
    else:
        body = "Generate a fun 45-second narrative consistent with the series theme."
    return SCRIPT_TMPL.format(title=title, series=plan["series"], body=body)

def synthesize_audio(text_path, out_wav):
    Path(out_wav).write_bytes(b"FAKE_WAV")
    return out_wav

def synthesize_visuals(assets_dir):
    (assets_dir / "bg.png").write_bytes(b"FAKE_PNG")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    plan_path = sorted(Path(f"out/{args.series}").glob("ep_*/plan.json"))[-1]
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    assets_dir = Path(plan_path).parent / "assets"
    assets_dir.mkdir(exist_ok=True)

    script_txt = synthesize_script(plan)
    (assets_dir / "script.txt").write_text(script_txt, encoding="utf-8")

    synthesize_visuals(assets_dir)
    synthesize_audio(assets_dir / "script.txt", assets_dir / "voice.wav")

    print(f"[gen] assets ready at {assets_dir}")

if __name__ == "__main__":
    main()
