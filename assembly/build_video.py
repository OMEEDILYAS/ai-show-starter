# assembly/build_video.py
import argparse, json, subprocess, sys
from pathlib import Path

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

def sh(cmd):
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        raise SystemExit(f"command failed: {cmd}")

def ffprobe_duration(path: Path) -> float:
    cmd = [
        FFP PROBE, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    try:
        return float(out)
    except:
        return 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    # locate plan and assets
    series_dir = Path("out") / args.series
    plan_path = sorted(series_dir.glob("ep_*/plan.json"))[-1]
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"
    final_dir = series_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    # inputs
    voice = assets / "voice.wav"
    overlay_txt = (assets / "overlay.txt")
    title_txt = (assets / "title.txt")

    if not voice.exists():
        raise SystemExit(f"voice track missing: {voice}")
    dur = ffprobe_duration(voice)
    if dur < 3.0:
        raise SystemExit(f"voice too short ({dur:.2f}s). need >= 3s")

    # load strings (fallbacks)
    overlay = overlay_txt.read_text(encoding="utf-8").strip() if overlay_txt.exists() else ""
    title = title_txt.read_text(encoding="utf-8").strip() if title_txt.exists() else "Daily Episode"

    # output
    out_mp4 = final_dir / f"{ep_dir.name}.mp4"

    # Build: 9:16 1080x1920 solid bg for 'dur' seconds; draw title and overlay; mux voice
    # fonts: use DejaVuSans (installed in workflow)
    draw = (
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{title[:64].replace(':','\\:').replace(\"'\",\"\\'\")}':"
        f"fontcolor=white:fontsize=64:x=(w-text_w)/2:y=120,"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{overlay[:120].replace(':','\\:').replace(\"'\",\"\\'\")}':"
        f"fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h-300"
    )

    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"color=size=1080x1920:rate=30:color=black",
        "-i", str(voice),
        "-t", f"{dur:.3f}",
        "-filter:v", draw,
        "-c:v", "libx264", "-profile:v", "baseline", "-level", "4.0", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(out_mp4)
    ]
    sh(cmd)

    # write a small marker to plan (optional)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["video_path"] = str(out_mp4)
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    print(f"[assembly] wrote {out_mp4} (dur≈{dur:.2f}s)")

if __name__ == "__main__":
    main()
