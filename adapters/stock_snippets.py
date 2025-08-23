# adapters/stock_snippets.py
import subprocess, shlex, random
from pathlib import Path

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

def _probe_duration(path: Path) -> float:
    try:
        out = subprocess.check_output(
            [FFPROBE, "-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", str(path)],
            text=True
        ).strip()
        return float(out)
    except Exception:
        return 0.0

def _pick_candidate(assets_dir: Path, keywords):
    files = list(assets_dir.glob("*.mp4"))
    if not files:
        return None
    # naive keyword scoring over filename
    kw = [k.lower() for k in (keywords or [])]
    def score(p: Path):
        name = p.name.lower()
        hits = sum(1 for k in kw if k in name)
        # prefer pexels/pixabay videos
        pref = 1 if ("pexels" in name or "pixabay" in name) else 0
        return (hits, pref)
    files.sort(key=score, reverse=True)
    return files[-1] if files else None

def make_stock_snip(assets_dir: Path, keywords, out: Path, dur: float):
    out.parent.mkdir(parents=True, exist_ok=True)
    candidate = _pick_candidate(assets_dir, keywords)
    if not candidate:
        return False

    # Normalize to vertical 1080x1920 and trim/pad to duration
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p"
    cmd = f'{FFMPEG} -y -i {shlex.quote(str(candidate))} -t {dur:.3f} -vf "{vf}" -an {shlex.quote(str(out))}'
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    return proc.returncode == 0
