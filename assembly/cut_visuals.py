# assembly/cut_visuals.py
import argparse, os, sys, subprocess, shutil
from pathlib import Path

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

def dur(path: Path) -> float:
    try:
        out = subprocess.check_output(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            text=True
        ).strip()
        return float(out)
    except Exception:
        return 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--min_total", type=float, default=40.0)  # seconds, target minimum
    ap.add_argument("--max_inputs", type=int, default=12)
    args = ap.parse_args()

    ep_dir = sorted((Path("out")/args.series).glob("ep_*"))[-1]
    assets = ep_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    voice = assets / "voice.wav"
    target = max(dur(voice), args.min_total) if voice.exists() else args.min_total

    # Candidate clips: prefer list file if present; otherwise glob pexels/*.mp4 in assets
    list_file = assets / "stock_list.txt"
    clips = []
    if list_file.exists():
        for line in list_file.read_text(encoding="utf-8").splitlines():
            p = Path(line.strip())
            if p.suffix.lower() == ".mp4" and p.exists():
                clips.append(p)
    else:
        for p in sorted(assets.glob("*.mp4")):
            if p.name.lower() == "bg.mp4":
                continue
            if "pexels" in p.name.lower():
                clips.append(p)

    # Fallback: if nothing found, do nothing (keep bg)
    if not clips:
        print("[cut_visuals] no stock clips found; skipping (bg.mp4 will be used).")
        return

    # Build a list that is long enough; just cycle until total duration >= target
    lengths = [dur(c) for c in clips]
    pairs = [(c, d) for c, d in zip(clips, lengths) if d > 0.4]  # ignore tiny/invalid
    if not pairs:
        print("[cut_visuals] all stock clips invalid; skipping.")
        return

    seq = []
    total = 0.0
    i = 0
    while total < target and len(seq) < args.max_inputs:
        c, d = pairs[i % len(pairs)]
        seq.append(c)
        total += d
        i += 1

    # ffmpeg concat via filter_complex; normalize each to 1080x1920 (9:16), 30fps
    visuals = assets / "visuals.mp4"

    # Inputs
    cmd = [FFMPEG, "-y"]
    for c in seq:
        cmd += ["-i", str(c)]

    # Per-input normalization chains -> [v0],[v1],...
    vlabels = []
    fc_parts = []
    for idx in range(len(seq)):
        in_label = f"[{idx}:v]"
        out_label = f"[v{idx}]"
        vlabels.append(out_label)
        fc_parts.append(
            f"{in_label}"
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,setsar=1,fps=30"
            f"{out_label}"
        )

    # Concat them (video only)
    n = len(seq)
    fc_parts.append(f"{''.join(vlabels)}concat=n={n}:v=1:a=0,format=yuv420p[v]")
    fc = ";".join(fc_parts)

    cmd += [
        "-filter_complex", fc,
        "-map", "[v]",
        "-t", f"{target:.3f}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        str(visuals)
    ]

    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    if proc.returncode != 0 or not visuals.exists():
        print("[cut_visuals] ffmpeg failed; leaving bg.mp4 fallback.", file=sys.stderr)
        sys.exit(0)

    print(f"[cut_visuals] wrote {visuals} (target≈{target:.1f}s)")

if __name__ == "__main__":
    main()
