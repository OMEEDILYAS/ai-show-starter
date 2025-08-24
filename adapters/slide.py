from pathlib import Path
import subprocess, json

FFMPEG = "ffmpeg"

def make(beat: dict, idx: int, ep_dir: Path) -> Path:
    assets = ep_dir / "assets"
    shots = assets / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    out = shots / f"{idx:03d}.mp4"

    bg = assets / "bg.mp4"
    title = beat.get("title") or (beat.get("text") or "SLIDE")[:120]
    body = beat.get("text") or ""

    overlay = (title + "\\n" + body.replace(":", "\\:")).replace("'", "\\'")
    cmd = [
        FFMPEG, "-y",
        "-i", str(bg),
        "-vf",
        f"format=yuv420p,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{overlay}':line_spacing=16:fontcolor=white:fontsize=48:x=80:y=160",
        "-t", str(max(1.5, beat.get('dur', 5.0))),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out)
    ]
    subprocess.check_call(cmd)
    return out
