# generator/route_shots.py
import argparse, json, os, subprocess, shlex, tempfile
from pathlib import Path

from adapters.slide_cards import make_slide
from adapters.diagram_basic import make_diagram
from adapters.stock_snippets import make_stock_snip

FFMPEG = "ffmpeg"

def concat_videos(paths, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # use concat demuxer
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        for p in paths:
            f.write(f"file '{Path(p).as_posix()}'\n")
        list_file = f.name
    cmd = f"{FFMPEG} -y -f concat -safe 0 -i {shlex.quote(list_file)} -c copy {shlex.quote(str(out_path))}"
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    if proc.returncode != 0 or not out_path.exists():
        # fallback re-encode
        vf = "format=yuv420p"
        cmd2 = f"{FFMPEG} -y -f concat -safe 0 -i {shlex.quote(list_file)} -vf {vf} -c:v libx264 -pix_fmt yuv420p -preset veryfast {shlex.quote(str(out_path))}"
        proc2 = subprocess.run(cmd2, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(proc2.stdout)
        if proc2.returncode != 0:
            raise SystemExit("[router] concat failed")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    series_dir = Path("out") / args.series
    plan = sorted(series_dir.glob("ep_*/plan.json"))[-1]
    ep_dir = plan.parent
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

    stock_pool = assets  # we already stage fetched stock into assets/

    made = []
    for i, b in enumerate(beats):
        t = (b.get("type") or "slide").lower()
        text = (b.get("text") or "").strip()[:80] or " "
        dur = max(3.0, min(8.0, float(b.get("dur") or 5)))
        kws = b.get("keywords") or []
        out = shots_dir / f"{i:03d}.mp4"

        try:
            if t in ("slide", "data_viz"):
                # simple card (we can specialize later)
                make_slide(text=text, out=out, dur=dur, title=None)
            elif t in ("diagram", "math"):
                make_diagram(text=text, keywords=kws, out=out, dur=dur)
            elif t in ("map","code"):
                # temp: use slide until we add real adapters
                make_slide(text=text, out=out, dur=dur, title=None)
            else:  # stock
                ok = make_stock_snip(stock_pool, kws, out, dur)
                if not ok:
                    make_slide(text=text, out=out, dur=dur)
        except SystemExit as e:
            print("[router] beat failed, fallback slide:", e)
            make_slide(text=text, out=out, dur=dur)

        if out.exists():
            made.append(str(out))

    if not made:
        print("[router] no shots produced; skipping visuals build")
        return

    visuals = assets / "visuals.mp4"
    concat_videos(made, visuals)
    print("[router] wrote", visuals)

if __name__ == "__main__":
    main()
