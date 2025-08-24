# generator/route_shots.py
import argparse, json, subprocess, shlex, tempfile, sys
from pathlib import Path

# Ensure adapters import works on GitHub Actions
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.slide_cards import make_slide
from adapters.diagram_basic import make_diagram
from adapters.stock_snippets import make_stock_snip

FFMPEG = "ffmpeg"

def concat_videos(paths, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    abs_paths = [str(Path(p).resolve()) for p in paths]

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        for p in abs_paths:
            f.write(f"file {shlex.quote(p)}\n")
        list_file = f.name

    # Try stream copy first (fast)
    cmd = f"{FFMPEG} -y -f concat -safe 0 -i {shlex.quote(list_file)} -c copy {shlex.quote(str(out_path.resolve()))}"
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)

    if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        # Fallback re-encode (robust)
        vf = "format=yuv420p"
        cmd2 = f"{FFMPEG} -y -f concat -safe 0 -i {shlex.quote(list_file)} -vf {vf} -c:v libx264 -pix_fmt yuv420p -preset veryfast {shlex.quote(str(out_path.resolve()))}"
        proc2 = subprocess.run(cmd2, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(proc2.stdout)
        if proc2.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            raise SystemExit("[router] concat failed")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    series_dir = Path("out") / args.series
    plans = sorted(series_dir.glob("ep_*/plan.json"))
    if not plans:
        print("[router] no plan.json found; nothing to route")
        return

    plan_path = plans[-1]
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"
    shots_dir = assets / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    shotlist_path = assets / "shotlist.json"
    if not shotlist_path.exists():
        print("[router] no shotlist.json; skipping (bg will be used)")
        return

    sl = json.loads(shotlist_path.read_text(encoding="utf-8"))
    beats = sl.get("beats") or []
    if not beats:
        print("[router] empty beats; skipping")
        return

    # Where we search for stock clips: anything already staged into assets/
    stock_pool = assets

    made = []
    for i, b in enumerate(beats):
        t = (b.get("type") or "slide").lower()
        text = (b.get("text") or "").strip()[:80] or " "
        dur = max(3.0, min(8.0, float(b.get("dur") or 5)))
        kws = b.get("keywords") or []
        out = shots_dir / f"{i:03d}.mp4"

        print(f"[router] beat {i}: {t} (kw={kws})")

        # 1) STOCK-FIRST: if we have keywords, try to find a matching clip
        used_stock = False
        if kws:
            try:
                if make_stock_snip(stock_pool, kws, out, dur):
                    used_stock = True
                    print(f"[router] beat {i}: used STOCK for keywords {kws} -> {out}")
            except SystemExit as e:
                print(f"[router] beat {i}: stock attempt failed ({e}); will fallback")

        # 2) If no stock used, render according to type (with graceful fallback)
        if not used_stock:
            try:
                if t in ("diagram", "math"):
                    make_diagram(text=text, keywords=kws, out=out, dur=dur)
                    print(f"[router] beat {i}: DIAGRAM -> {out}")
                else:
                    # slide, data_viz, map, code, unknown → simple slide card
                    make_slide(text=text, out=out, dur=dur, title=None)
                    print(f"[router] beat {i}: SLIDE -> {out}")
            except SystemExit as e:
                print(f"[router] beat {i}: type render failed ({e}); fallback SLIDE")
                make_slide(text=text, out=out, dur=dur, title=None)

        if out.exists() and out.stat().st_size > 0:
            made.append(str(out.resolve()))
        else:
            print(f"[router] beat {i}: output missing/empty -> {out}")

    if not made:
        print("[router] no shots produced; skipping visuals build")
        return

    visuals = assets / "visuals.mp4"
    print("[router] shots:", *[f"  - {p}" for p in made], sep="\n")
    concat_videos(made, visuals)
    print("[router] wrote", visuals)

if __name__ == "__main__":
    main()