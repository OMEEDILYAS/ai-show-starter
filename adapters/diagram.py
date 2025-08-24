from pathlib import Path
import subprocess

FFMPEG = "ffmpeg"

def make(beat: dict, idx: int, ep_dir: Path) -> Path:
    assets = ep_dir / "assets"
    shots = assets / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    out = shots / f"{idx:03d}.mp4"

    bg = assets / "bg.mp4"
    # Use keywords as “nodes” text block so it’s visibly different from slide
    kws = beat.get("keywords") or []
    block = " • " + "\\n • ".join(kws) if kws else "DIAGRAM"
    overlay = ("DIAGRAM\\n" + block).replace("'", "\\'")
    cmd = [
        FFMPEG, "-y",
        "-i", str(bg),
        "-vf",
        f"format=yuv420p,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{overlay}':line_spacing=12:fontcolor=white:fontsize=46:x=(w-text_w)/2:y=(h-text_h)/2",
        "-t", str(max(1.5, beat.get('dur', 5.0))),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out)
    ]
    subprocess.check_call(cmd)
    return out
