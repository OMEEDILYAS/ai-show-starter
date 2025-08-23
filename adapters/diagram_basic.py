# adapters/diagram_basic.py
import subprocess, shlex
from pathlib import Path

FFMPEG = "ffmpeg"

def make_diagram(text: str, keywords, out: Path, dur: float):
    out.parent.mkdir(parents=True, exist_ok=True)
    kw = " • ".join([k[:12] for k in (keywords or [])])
    caption = text.replace(":", r"\:").replace("'", r"\'")
    kwtxt = kw.replace(":", r"\:").replace("'", r"\'")
    draw = [
        # header bar
        "drawbox=x=0:y=0:w=1080:h=160:color=0x1e2a37@1:t=fill",
        # header keywords
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{kwtxt}':fontcolor=white:fontsize=44:x=40:y=60",
        # center caption (pretend diagram label)
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{caption}':fontcolor=white:fontsize=52:x=(w-text_w)/2:y=(h-text_h)/2"
    ]
    vf = "format=yuv420p," + ",".join(draw)
    cmd = f"{FFMPEG} -y -f lavfi -i color=c=0x0e1116:s=1080x1920:r=30 -t {dur:.3f} -vf \"{vf}\" -an {shlex.quote(str(out))}"
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        raise SystemExit("[diagram] ffmpeg failed")
