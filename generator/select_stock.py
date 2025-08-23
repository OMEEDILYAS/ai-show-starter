# generator/select_stock.py
import argparse, json, os, random, re, subprocess
from pathlib import Path

FFPROBE = "ffprobe"

def probe_dur(p: Path) -> float:
    try:
        out = subprocess.check_output(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", str(p)],
            text=True
        ).strip()
        return float(out)
    except Exception:
        return 0.0

def tokens_from(text: str) -> set:
    words = re.findall(r"[a-z0-9_]+", (text or "").lower())
    return set(words)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--max_clips", type=int, default=6)
    args = ap.parse_args()

    series = args.series
    out_dir = Path("out") / series
    plan_path = sorted(out_dir.glob("ep_*/plan.json"))[-1]
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    # Pull topic cues
    cues = " ".join([
        plan.get("ai_title",""),
        plan.get("ai_overlay",""),
        plan.get("ai_narration",""),
        plan.get("title",""),
        plan.get("theme","")
    ])
    tok = tokens_from(cues)

    # Gather candidate files
    roots = [Path("assets/stock/common"), Path(f"assets/stock/{series}")]
    files = []
    for r in roots:
        if r.exists():
            for p in r.glob("**/*.mp4"):
                files.append(p)

    if not files:
        print("[stock] no stock files found; skipping visuals")
        return

    # Score by simple tag overlap (filename tokens)
    scored = []
    for p in files:
        name_tok = tokens_from(p.stem)
        score = len(tok & name_tok)
        dur = probe_dur(p)
        scored.append((score, dur, p))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # Keep clips with nonzero score first, then fill with others
    nonzero = [t for t in scored if t[0] > 0]
    zero = [t for t in scored if t[0] == 0]
    picked = (nonzero + zero)[:args.max_clips]
    picked_paths = [p for _,_,p in picked]

    # Save list for cutter
    lst = assets / "stock_list.txt"
    lst.write_text("\n".join(str(p) for p in picked_paths), encoding="utf-8")

    print("[stock] picked:")
    for p in picked_paths:
        print(" -", p)

if __name__ == "__main__":
    main()
