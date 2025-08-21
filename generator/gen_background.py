# generator/gen_background.py
import argparse, subprocess, sys
from pathlib import Path

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

def ffprobe_duration(path: Path) -> float:
    out = subprocess.check_output([
        FFPROBE, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ], text=True).strip()
    try:
        return float(out)
    except Exception:
        return 0.0

def sh(args):
    print("+", " ".join(args))
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(p.stdout)
    if p.returncode != 0:
        sys.exit(p.returncode)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    series_dir = Path("out") / args.series
    plan_path = sorted(series_dir.glob("ep_*/plan.json"))[-1]
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    voice = assets / "voice.wav"
    if not voice.exists():
        raise SystemExit(f"Missing voice at {voice}")
    dur = ffprobe_duration(voice)
    if dur < 3:
        raise SystemExit(f"Voice too short ({dur:.2f}s)")

    bg = assets / "bg.mp4"

    # Abstract animated background:
    # testsrc2 -> strong blur -> slight saturation boost -> yuv420p
    # 1080x1920 @ 30fps, duration matches narration
    filter_chain = "boxblur=20:1,eq=saturation=1.25,format=yuv420p"
    sh([
        FFMPEG, "-y",
        "-f", "lavfi",
        "-i", f"testsrc2=size=1080x1920:rate=30",
        "-t", f"{dur:.3f}",
        "-vf", filter_chain,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        str(bg)
    ])
    print(f"[bg] wrote {bg} ({dur:.2f}s)")

if __name__ == "__main__":
    main()
