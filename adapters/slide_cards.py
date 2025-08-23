# adapters/slide_cards.py
import subprocess, shlex
from pathlib import Path

FFMPEG = "ffmpeg"

def make_slide(text: str, out: Path, dur: float, title: str = ""):
    out.parent.mkdir(parents=True, exist_ok=True)
    overlay = text.replace(":", r"\:").replace("'", r"\'")
    title = (title or "").replace(":", r"\:").replace("'", r"\'")
    # background color matches your current palette
    draw = []
    if title:
        draw.append(
            "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"text='{title}':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=120"
        )
    draw.append(
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{overlay}':fontcolor=white:fontsize=48:"
        "x=(w-text_w)/2:y=(h-text_h)/2"
    )
    vf = "format=yuv420p," + ",".join(draw)
    cmd = f"{FFMPEG} -y -f lavfi -i color=c=0x101426:s=1080x1920:r=30 -t {dur:.3f} -vf \"{vf}\" -an {shlex.quote(str(out))}"
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        raise SystemExit("[slide] ffmpeg failed")
