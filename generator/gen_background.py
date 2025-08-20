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

def sh(cmd):
    print("+", " ".join(cmd))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
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

    # Animated, loopable background: gradient + noise + blur + subtle zoom
    # 1080x1920, 30fps
    filter_graph = (
        "color=black:size=1080x1920:rate=30,format=yuv420p [base];"
        "nullsrc=size=1080x1920,geq='r(X,Y)=X+Y:g(X,Y)=Y:b(X,Y)=X',"
        "format=yuv420p,boxblur=10:1,setsar=1,scale=1080:1920 [grad];"
        "noise=c0s=20:c0f=t+u,format=yuv420p,boxblur=2:1,scale=1080:1920 [noise];"
        "[grad][noise] blend=all_mode=softlight:all_opacity=0.35,zoompan="
        "'z=1+0.02*t:x=(iw-iw/zoom)/2:y=(ih-ih/zoom)/2:d=30*%0.3f:s=1080x1920'"
        % dur
    )

    sh([
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-f", "lavfi", "-i", filter_graph,
        "-t", f"{dur:.3f}",
        "-shortest",
        "-map", "1:v:0",
        "-map", "0:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "96k",
        str(bg)
    ])
    print(f"[bg] wrote {bg} ({dur:.2f}s)")

if __name__ == "__main__":
    main()
