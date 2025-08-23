# assembly/cut_visuals.py
import argparse, json, os, subprocess
from pathlib import Path

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

def ffprobe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(path)], text=True
    ).strip()
    try: return float(out)
    except: return 0.0

def sh(cmd):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    series_dir = Path("out") / args.series
    plan_path = sorted(series_dir.glob("ep_*/plan.json"))[-1]
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"
    final_dir = series_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    voice = assets / "voice.wav"
    target = ffprobe_duration(voice) if voice.exists() else 50.0

    stock_list = assets / "stock_list.txt"
    if not stock_list.exists():
        print("[cut] no stock_list.txt; skipping visuals")
        return
    with stock_list.open() as f:
        clips = [Path(x.strip()) for x in f if x.strip()]

    if not clips:
        print("[cut] empty list; skipping visuals")
        return

    # Convert each to vertical 1080x1920 with gentle zoom (if not already)
    work = assets / "work"
    work.mkdir(exist_ok=True)
    prepared = []
    for i, src in enumerate(clips, start=1):
        out = work / f"prep_{i:02d}.mp4"
        vf = (
            "scale=w=1080:h=-2:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(1080-iw)/2:(1920-ih)/2:black,"
            "zoompan=z='1+0.02*t':d=30*5:s=1080x1920"
        )
        cmd = [FFMPEG, "-y", "-i", str(src),
               "-vf", vf, "-r", "30",
               "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
               str(out)]
        try:
            sh(cmd)
            prepared.append(out)
        except subprocess.CalledProcessError:
            print("[cut] failed on", src)

    if not prepared:
        print("[cut] no prepared clips; skipping visuals")
        return

    # Decide per-clip length to reach target with crossfades (~0.4s)
    n = len(prepared)
    if n == 1:
        per = target
    else:
        per = max(3.0, (target + 0.4*(n-1)) / n)

    # Trim each and build a concat script
    trimmed = []
    for i, src in enumerate(prepared, start=1):
        out = work / f"trim_{i:02d}.mp4"
        cmd = [FFMPEG, "-y", "-i", str(src),
               "-t", f"{per:.3f}", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-preset", "veryfast", str(out)]
        sh(cmd)
        trimmed.append(out)

    # Crossfade chain
    # v0 xf v1 -> v01 ; v01 xf v2 -> v02 ; ...
    cur = trimmed[0]
    for i in range(1, len(trimmed)):
        nxt = trimmed[i]
        out = work / f"xf_{i:02d}.mp4"
        # 0.4s crossfade starting at end-0.4 of first
        filter_complex = (
            "[0:v][1:v]xfade=transition=fade:duration=0.4:offset=PTS-STARTPTS+"
            f"{max(0.0, per-0.4):.3f}"
        )
        cmd = [FFMPEG, "-y",
               "-i", str(cur), "-i", str(nxt),
               "-filter_complex", filter_complex,
               "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
               str(out)]
        sh(cmd)
        cur = out

    # Output visuals.mp4
    visuals = assets / "visuals.mp4"
    cmd = [FFMPEG, "-y", "-i", str(cur),
           "-t", f"{target:.3f}", "-an",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
           str(visuals)]
    sh(cmd)
    print("[cut] wrote", visuals)

if __name__ == "__main__":
    main()
