# assembly/validate_video.py
import argparse, subprocess, sys, json
from pathlib import Path

FFPROBE = "ffprobe"

def ffprobe_stream_info(path: Path):
    """Return (width, height, vcodec) for the first video stream."""
    cmd = [
        FFPROBE, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name",
        "-of", "json",
        str(path)
    ]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    streams = data.get("streams", [])
    if not streams:
        raise SystemExit(f"No video stream found in {path}")
    s0 = streams[0]
    w = int(s0.get("width", 0))
    h = int(s0.get("height", 0))
    vcodec = s0.get("codec_name", "")
    return w, h, vcodec

def ffprobe_duration(path: Path) -> float:
    """Return container duration in seconds (float)."""
    cmd = [
        FFPROBE, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(path)
    ]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    dur = float(data.get("format", {}).get("duration", 0.0))
    return dur

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    final_dir = Path("out") / args.series / "final"
    mp4s = sorted(final_dir.glob("*.mp4"))
    if not mp4s:
        raise SystemExit(f"No final mp4 in {final_dir}")

    vid = mp4s[-1]
    w, h, vcodec = ffprobe_stream_info(vid)
    dur = ffprobe_duration(vid)

    problems = []
    # Size/aspect: 1080x1920 (9:16) for Reels/TikTok
    if not (w == 1080 and h == 1920):
        problems.append(f"expected 1080x1920 (9:16), got {w}x{h}")
    if vcodec not in ("h264", "libx264"):
        problems.append(f"video codec not H.264 (got {vcodec})")
    if dur < 30 or dur > 90:
        problems.append(f"duration {dur:.2f}s not in [30..90]s")

    if problems:
        print(f"[validate] {vid} failed:")
        for p in problems:
            print(" -", p)
        sys.exit(1)

    print(f"[validate] OK: {vid} {w}x{h} {vcodec} {dur:.2f}s")

if __name__ == "__main__":
    main()
