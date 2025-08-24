# generator/route_shots.py
import argparse, json, os, subprocess, shlex, tempfile, sys, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.slide_cards import make_slide
from adapters.diagram_basic import make_diagram

FFMPEG = "ffmpeg"

def run(cmd: str):
    print("+", cmd)
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        raise SystemExit(f"[router] command failed: {cmd}")

def concat_videos(paths, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    abs_paths = [str(Path(p).resolve()) for p in paths]
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        for p in abs_paths:
            f.write(f"file {shlex.quote(p)}\n")
        list_file = f.name

    # try stream copy
    cmd = f"{FFMPEG} -y -f concat -safe 0 -i {shlex.quote(list_file)} -c copy {shlex.quote(str(out_path.resolve()))}"
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    if proc.returncode != 0 or not out_path.exists():
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

def _tokens_from_name(p: Path):
    base = p.stem.lower()
    toks = re.split(r"[^a-z0-9]+", base)
    return {t for t in toks if t}

def _series_default_tags(series: str):
    base = series.lower()
    if "teacher" in base:
        return {"math","vector","matrix","algebra","geometry","lesson","education"}
    if "drama" in base:
        return {"dialog","scene","city","night","mood"}
    if "meme" in base or "memes" in base:
        return {"meme","reaction","funny","emoji","caption"}
    return {base}

def load_stock_index(assets_dir: Path, series: str):
    """
    Build [(Path, set(tags))] from:
      - assets/fetched_list.txt (either 'path' or 'path | tag1, tag2')
      - any *.mp4 in assets_dir as extras
    """
    idx = {}
    fl = assets_dir / "fetched_list.txt"
    if fl.exists():
        for line in fl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                p_str, tags_str = [x.strip() for x in line.split("|", 1)]
                tags = {t.strip().lower() for t in tags_str.split(",") if t.strip()}
            else:
                p_str = line
                tags = set()
            p = Path(p_str)
            if not p.exists():
                continue
            if not tags:
                tags = _tokens_from_name(p)
                tags |= _series_default_tags(series)
            idx[p] = tags

    # also sweep any mp4s in assets/ as fallbacks
    for p in assets_dir.glob("*.mp4"):
        if p not in idx and p.name != "bg.mp4":
            tags = _tokens_from_name(p) | _series_default_tags(series)
            idx[p] = tags

    out = [(p, tags) for p, tags in idx.items()]
    print(f"[router] stock candidates: {len(out)}")
    return out

def best_stock_for(keywords, index):
    kw = {k.lower() for k in (keywords or []) if k}
    if not kw:
        return None
    best, best_overlap = None, 0
    for p, tags in index:
        ov = len(kw & tags)
        if ov > best_overlap:
            best, best_overlap = p, ov
    return best

def make_stock_clip(src: Path, out: Path, dur: float):
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        "scale='if(gt(a,9/16),-2,1080)':'if(gt(a,9/16),1920,-2)',"
        "crop=1080:1920,format=yuv420p"
    )
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

    stock_index = load_stock_index(assets, args.series)

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
                make_stock_clip(pick, out, dur)
                print(f"[router] beat {i}: stock -> {pick.name} (kw={kws})")
            elif t in ("diagram", "math"):
                make_diagram(text=text, keywords=kws, out=out, dur=dur)
                print(f"[router] beat {i}: diagram (kw={kws})")
            else:
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
