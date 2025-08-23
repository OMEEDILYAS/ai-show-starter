# planner/make_shotlist.py
import argparse, json, os
from pathlib import Path
import requests

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

SYS = """You convert short narration into a compact shot list for a vertical 9:16 video.
Return JSON with key "beats": an array of beats:
- start (seconds, integer), dur (seconds, integer 3-8)
- type: one of [slide, diagram, data_viz, map, code, stock]
- keywords: 3-6 concise words to drive visuals
- text: 5-12 word on-screen text (no emojis/hashtags)
Rules: Keep total length ≈ narration length (45–60s). Prefer slide/diagram over stock when possible.
"""

USER_TMPL = """Narration:
{narr}

Make ~7-10 beats, each 4-7s. Emphasize topic alignment. If math terms (vector, matrix, eigen), use type=diagram.
"""

def call_openai(narration: str):
    if not OPENAI_API_KEY:
        # fallback: naive evenly-split slides
        words = narration.split()
        chunk = max(1, len(words)//8)
        beats = []
        for i in range(8):
            seg = " ".join(words[i*chunk:(i+1)*chunk]) or "Keep watching!"
            beats.append({"start": i*6, "dur": 6, "type": "slide", "keywords": ["general","topic"], "text": seg[:40]})
        return {"beats": beats}

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": MODEL,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role":"system","content":SYS},
            {"role":"user","content":USER_TMPL.format(narr=narration)}
        ],
        "temperature": 0.5,
    }
    r = requests.post(url, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    # find latest episode assets
    series_dir = Path("out") / args.series
    plan = sorted(series_dir.glob("ep_*/plan.json"))[-1]
    ep_dir = plan.parent
    assets = ep_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    narr_path = assets / "narration.txt"
    narration = narr_path.read_text(encoding="utf-8").strip() if narr_path.exists() else "Welcome to today's episode."

    data = call_openai(narration)
    (assets / "shotlist.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("[shotlist] wrote", assets / "shotlist.json")

if __name__ == "__main__":
    main()
