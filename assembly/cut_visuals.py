# assembly/cut_visuals.py
import argparse, subprocess, shlex, json
from pathlib import Path

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

def dur_seconds(path: Path) -> float:
    if not path.exists():
        return 0.0
    cmd = f'{FFPROBE} -v error -show_entries format=duration -of default=nk=1:nw=1 {shlex.quote(str(path))}'
    out = subprocess.check_output(cmd, shell=True, text=True).strip()
    try:
        return float(out)
    except:
        return 0.0

def ff_concat(paths, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Build concat filter with safe re-encode (uniform yuv420p)
    inputs = " ".join(f'-i {shlex.quote(str(p))}' for p in paths)
    filters = "".join(f'[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,'
                      f'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p[v{i}];'
                      for i in range(len(paths)))
    concat = "".join(f'[v{i}]' for i in range(len(paths))) + f'concat=n={len(paths)}:v=1:a=0[outv]'
    cmd = f'{FFMPEG} -y {inputs} -filter_complex "{filters}{concat}" -map "[outv]" -r 30 -c:v libx264 -preset veryfast -pix_fmt yuv420p {shlex.quote(str(out_path))}'
    run = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(run.stdout)
    if run.returncode != 0:
        raise SystemExit("[cut_visuals] concat failed")

def ff_trim(in_path: Path, out_path: Path, seconds: float):
    cmd = f'{FFMPEG} -y -i {shlex.quote(str(in_path))} -t {seconds:.3f} -c copy {shlex.quote(str(out_path))}'
    run = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(run.stdout)
    if run.returncode != 0:
        # fallback re-encode if stream copy can’t cut cleanly
        cmd2 = f'{FFMPEG} -y -i {shlex.quote(str(in_path))} -t {seconds:.3f} -c:v libx264 -preset veryfast -pix_fmt yuv420p {shlex.quote(str(out_path))}'
        run2 = subprocess.run(cmd2, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(run2.stdout)
        if run2.returncode != 0:
            raise SystemExit("[cut_visuals] trim failed")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    series_dir = Path("out") / args.series
    plan = sorted(series_dir.glob("ep_*/plan.json"))[-1]
    ep_dir = plan.parent
    assets = ep_dir / "assets"

    voice = assets / "voice.wav"
    visuals = assets / "visuals.mp4"
    target = dur_seconds(voice)
    if target <= 0:
        # try narration.txt timestamps? If none, just skip trim.
        print("[cut_visuals] WARN: voice.wav missing or duration=0; skipping trim.")
        return

    if visuals.exists():
        # Prefer router visuals → just trim
        print("[cut_visuals] trimming router visuals to narration length…")
        tmp = visuals.with_suffix(".trim.mp4")
        ff_trim(visuals, tmp, target)
        tmp.replace(visuals)
        print("[cut_visuals] done (router visuals).")
        return

    # Fallback: build visuals from stock list, then trim
    stock_list = assets / "stock_list.txt"
    picks = []
    if stock_list.exists():
        picks = [Path(line.strip()) for line in stock_list.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not picks:
        # scan assets for fetched stock
        picks = sorted(assets.glob(f"{args.series}_pexels_*.mp4")) + sorted(assets.glob(f"{args.series}_pixabay_*.mp4"))

    if not picks:
        raise SystemExit("[cut_visuals] no router visuals and no stock; nothing to do.")

    print("[cut_visuals] building visuals from stock picks:", *[str(p) for p in picks], sep="\n  - ")
    ff_concat(picks, visuals)

    # trim to narration
    tmp = visuals.with_suffix(".trim.mp4")
    ff_trim(visuals, tmp, target)
    tmp.replace(visuals)
    print("[cut_visuals] done (stock fallback).")

if __name__ == "__main__":
    main()
