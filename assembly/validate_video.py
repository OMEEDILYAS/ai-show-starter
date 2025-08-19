# assembly/validate_video.py
import argparse, subprocess, sys
from pathlib import Path

FFPROBE = "ffprobe"

def probe(path):
    cmd = [
        FFPROBE, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    out = subprocess.check_output(cmd, text=True).strip().splitlines()
    # order: width, height, vcodec, duration
    if len(out) < 4:
        raise SystemExit(f"ffprobe gave unexpected output for {path}:\n{out}")
    w = int(out[0]); h = int(out[1]); vcodec = out[2]; dur = float(out[3])
    return w, h, vcodec, dur

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    final_glob = Path("out") / args.series / "final"
    mp4s = sorted(final_glob.glob("*.mp4"))
    if not mp4s:
        raise SystemExit(f"No final mp4 in {final_glob}")

    vid = mp4s[-1]
    w, h, vcodec, dur = probe(vid)
    problems = []

    if not (h * 9 == w * 16 and w == 1080 and h == 1920):
        problems.append(f"aspect not 9:16 or wrong size (got {w}x{h})")
    if vcodec not in ("h264", "libx264"):
        problems.append(f"video codec not H.264 (got {vcodec})")
    if dur < 30 or dur > 90:
        problems.append(f"duration {dur:.2f}s not in [30..90]s")

    if problems:
        print(f"[validate] {vid} failed checks:")
        for p in problems:
            print(" -", p)
        sys.exit(1)

    print(f"[validate] OK: {vid} {w}x{h} {vcodec} {dur:.2f}s")

if __name__ == "__main__":
    main()
