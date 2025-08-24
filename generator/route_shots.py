# generator/route_shots.py
import argparse, json, os, subprocess, shlex, tempfile, sys
from pathlib import Path

# --- ensure local imports (adapters/*) work ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# ----------------------------------------------

from adapters.slide_cards import make_slide
from adapters.diagram_basic import make_diagram
# keep available as a fallback helper if you want; we won't rely on it for matching
# from adapters.stock_snippets import make_stock_snip

FFMPEG = "ffmpeg"

def run(cmd: str):
    """Run a shell command, print output, raise on failure."""
    print("+", cmd)
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        raise SystemExit(f"[router] command failed: {cmd}")

def concat_videos(paths, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # absolute paths so ffmpeg ignores temp file dir
    abs_paths = [str(Path(p).resolve()) for p in paths]

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        for p in abs_paths:
            f.write(f"file {shlex.quote(p)}\n")
        list_file = f.name

    # try stream copy first
    cmd = f"{FFMPEG} -y -f concat -safe 0 -i {shlex.quote(list_file)} -c copy {shlex.quote(str(out_path.resolve()))}"
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    if proc.returncode != 0 or not out_path.exists():
        # fallback re-encode to standard vertical format
        vf = "format=yuv420p"
        cmd2 = (
            f"{FFMPEG} -y -f concat -safe 0 -i {shlex.quote(list_file)} "
            f"-vf {vf} -r 30 -c:v libx264 -pix_fmt yuv420p -preset veryfast "
            f"{shlex.quote(str(out_path.resolve()))}"
        )
        proc2 = subprocess.run(cmd2, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(proc2.stdout)
        if proc2.returncode != 0:
            raise SystemExit("[router] concat failed")

def load_stock_index(assets_dir: Path):
    """
    Read fetched_list.txt -> [(Path, set(tags))]
    Lines expected as: /path/to.mp4 | tag1, tag2, tag3
    """
    idx = []
    fl = assets_dir / "fetched_list.txt"
    if fl.exists():
        for line in fl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|", 1)]
            if len(parts) == 2:
                p = Path(parts[0])
                tags = set(t.strip().lower() for t in parts[1].split(",") if t.strip())
                if p.exists():
                    idx.append((p, tags))
    return idx

def best_stock_for(keywords, index):
    """Pick the stock clip with the largest tag overlap with keywords."""
    kw = set(k.lower() for k in (keywords or []))
    if not kw or not index:
        return None
    best = None
    best_overlap = 0
    for p, tags in index:
        overlap = len(kw & tags)
        if overlap > best_overlap:
            best = p
            best_overlap = overlap
    return best

def make_stock_clip(src: Path, out: Path, dur: float):
    """
    Cut/loop a stock clip to duration 'dur', scale+crop to 1080x1920 (cover),
    30fps, h264, yuv420p.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    # Cover scale: if input aspect > 9/16, scale h to 1920; else scale w to 1080, then crop
    vf = (
        "scale="
        "'if(gt(a,9/16),-2,1080)':'if(gt(a,9/16),1920,-2)',"
        "crop=1080:1920,"
        "format=yuv420p"
    )
    # Use -stream_loop -1 to loop if src shorter than dur
    cmd = (
        f"{FFMPEG} -y -stream_loop -1 -i {shlex.quote(str(src))} "
        f"-t {dur:.3f} -r 30 -an -vf {vf} "
        f"-c:v libx264 -pix_fmt yuv420p -preset veryfast "
        f"{shlex.quote(str(out))}"
    )
    run(cmd)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    series_dir = Path("out") / args.series
    plans = sorted(series_dir.glob("ep_*/plan.json"))
    if not plans:
        print("[router] no plan.json; skipping")
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

    # Build stock index from fetched_list.txt (written by fetch_stock.py)
    stock_index = load_stock_index(assets)
    print(f"[router] stock candidates: {len(stock_index)}")

    made = []
    for i, b in enumerate(beats):
        t = (b.get("type") or "auto").lower()
        text = (b.get("text") or "").strip()[:80] or " "
        dur = max(3.0, min(8.0, float(b.get("dur") or 5)))
        kws = b.get("keywords") or []
        out = shots_dir / f"{i:03d}.mp4"

        try:
            pick = None
            if t in ("auto", "stock"):
                pick = best_stock_for(kws, stock_index)

            if pick is not None:
                # Use best-matching stock clip
                make_stock_clip(pick, out, dur)
                print(f"[router] beat {i}: stock -> {pick.name} (kw={kws})")
            elif t in ("diagram", "math"):
                make_diagram(text=text, keywords=kws, out=out, dur=dur)
                print(f"[router] beat {i}: diagram (kw={kws})")
            else:
                # slide as universal fallback
                make_slide(text=text, out=out, dur=dur, title=None)
                print(f"[router] beat {i}: slide (kw={kws})")
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
