# generator/select_stock.py
import argparse, shutil, re, random
from pathlib import Path

TAGS = {
    # add more tags/folders as you build your library
    "vectors": ["vector", "arrow", "geometry"],
    "matrix": ["matrix", "grid", "numbers"],
    "algebra": ["algebra", "math", "chalkboard"],
    "space": ["space", "cosmos", "stars", "nebula"],
    "tech": ["ai", "robot", "circuit", "hud"],
    "abstract": ["abstract", "loop", "gradient", "liquid"],
}

def extract_keywords(text: str):
    text = text.lower()
    words = set(re.findall(r"[a-z]{3,}", text))
    return words

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--max_clips", type=int, default=6)
    args = ap.parse_args()

    series_dir = Path("out") / args.series
    plan_path = sorted(series_dir.glob("ep_*/plan.json"))[-1]
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"
    stock_root = Path("assets") / "stock"  # your library root
    sel_dir = assets / "stock_sel"
    sel_dir.mkdir(parents=True, exist_ok=True)

    title = (assets / "title.txt").read_text(encoding="utf-8") if (assets / "title.txt").exists() else ""
    overlay = (assets / "overlay.txt").read_text(encoding="utf-8") if (assets / "overlay.txt").exists() else ""
    narration = (assets / "narration.txt").read_text(encoding="utf-8") if (assets / "narration.txt").exists() else ""
    words = extract_keywords(" ".join([title, overlay, narration]))

    # Find candidate tag folders
    tag_scores = []
    for tag, hints in TAGS.items():
        score = sum(1 for h in hints if h in words)
        if score > 0:
            tag_scores.append((score, tag))
    tag_scores.sort(reverse=True)

    # Build candidate file list
    candidates = []
    if tag_scores:
        for _, tag in tag_scores:
            candidates += list((stock_root / tag).glob("*.mp4"))
    # always add some abstracts as fallback
    candidates += list((stock_root / "abstract").glob("*.mp4"))

    # unique, sample
    seen = set()
    uniq = []
    for p in candidates:
        if p not in seen:
            uniq.append(p); seen.add(p)
    random.shuffle(uniq)
    picks = uniq[: args.max_clips]

    # copy into episode
    for i, src in enumerate(picks):
        dst = sel_dir / f"clip_{i:02d}.mp4"
        shutil.copy2(src, dst)

    print(f"[stock] selected {len(picks)} clips into {sel_dir}")

if __name__ == "__main__":
    main()
