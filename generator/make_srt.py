# generator/make_srt.py
import argparse, math
from pathlib import Path
import subprocess

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

def fmt_ts(t: float) -> str:
    h = int(t // 3600); t -= h*3600
    m = int(t // 60);   t -= m*60
    s = int(t);         ms = int((t - s) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    series_dir = Path("out") / args.series
    plan_path = sorted(series_dir.glob("ep_*/plan.json"))[-1]
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"

    voice = assets / "voice.wav"
    narration_txt = assets / "narration.txt"
    srt_path = assets / "subtitles.srt"

    if not voice.exists() or not narration_txt.exists():
        raise SystemExit("voice.wav or narration.txt missing")

    dur = ffprobe_duration(voice)
    text = " ".join(narration_txt.read_text(encoding="utf-8").split())
    words = text.split()
    if not words:
        raise SystemExit("Empty narration")

    wps = 2.2  # words per second (≈130 wpm)
    chunk = 7  # words per subtitle line
    idx = 1
    t = 0.0
    lines = []

    for i in range(0, len(words), chunk):
        piece = " ".join(words[i: i+chunk])
        seg_len = max(len(piece.split()) / wps, 0.8)  # min 0.8s per line
        start = t
        end = min(t + seg_len, dur - 0.05)
        if end <= start:
            break
        lines.append(f"{idx}\n{fmt_ts(start)} --> {fmt_ts(end)}\n{piece}\n")
        idx += 1
        t = end

    srt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[srt] wrote {srt_path} ({idx-1} cues, dur≈{dur:.2f}s)")

if __name__ == "__main__":
    main()
