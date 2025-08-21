# assembly/cut_visuals.py
import argparse, subprocess, sys, tempfile
from pathlib import Path

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

def sh(cmd):
    print("+", " ".join(cmd))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(p.stdout)
    if p.returncode != 0:
        sys.exit(p.returncode)

def ffprobe_duration(path: Path) -> float:
    out = subprocess.check_output([
        FFPROBE, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ], text=True).strip()
    try: return float(out)
    except: return 0.0

def normalize_clip(src: Path, dst: Path):
    # Center-crop to 9:16 with smart scale, mute audio, 30fps, yuv420p
    vf = (
        "scale='if(gt(a,9/16),-2,1080)':'if(gt(a,9/16),1920,-2)',"
        "crop=1080:1920,format=yuv420p,fps=30"
    )
    sh([FFMPEG, "-y", "-i", str(src), "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", str(dst)])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    series_dir = Path("out") / args.series
    plan_path = sorted(series_dir.glob("ep_*/plan.json"))[-1]
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"
    voice = assets / "voice.wav"
    sel_dir = assets / "stock_sel"
    out_visuals = assets / "visuals.mp4"

    if not sel_dir.exists():
        print("[cut] no stock_sel directory; skipping")
        return
    clips = sorted(sel_dir.glob("clip_*.mp4"))
    if not clips:
        print("[cut] no selected stock clips; skipping")
        return
    if not voice.exists():
        raise SystemExit("voice.wav missing")
    target = ffprobe_duration(voice)
    if target < 3:
        raise SystemExit(f"voice too short ({target:.2f}s)")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        norm = []
        # normalize all to consistent codec/size
        for i, src in enumerate(clips):
            dst = td / f"n_{i:02d}.mp4"
            normalize_clip(src, dst)
            norm.append(dst)

        # loop normalized clips until we exceed target a bit
        seq = []
        total = 0.0
        i = 0
        while total < target + 2 and norm:
            p = norm[i % len(norm)]
            d = ffprobe_duration(p)
            if d <= 0.1:
                i += 1; continue
            seq.append((p, d))
            total += d
            i += 1

        # write concat list
        concat_txt = td / "concat.txt"
        with concat_txt.open("w", encoding="utf-8") as f:
            for p, _ in seq:
                f.write(f"file '{p}'\n")

        # concat (stream copy) then trim to target and re-mux faststart
        concat_out = td / "concat.mp4"
        sh([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(concat_out)])
        sh([FFMPEG, "-y", "-i", str(concat_out), "-t", f"{target:.3f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-an", "-movflags", "+faststart", str(out_visuals)])

    print(f"[cut] wrote {out_visuals} (≈{target:.2f}s)")

if __name__ == "__main__":
    main()
