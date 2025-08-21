# assembly/build_video.py
import argparse, json, subprocess, sys, random, tempfile
from pathlib import Path

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

def sh(cmd):
    print("+", " ".join(cmd))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(p.stdout)
    if p.returncode != 0:
        raise SystemExit(p.returncode)

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

    voice   = assets / "voice.wav"
    visuals = assets / "visuals.mp4"      # preferred if present (stock/cut mix)
    bg      = assets / "bg.mp4"           # fallback animated background
    srt     = assets / "subtitles.srt"
    overlay_txt = assets / "overlay.txt"
    title_txt   = assets / "title.txt"

    if not voice.exists():
        raise SystemExit("Missing voice.wav")
    dur = ffprobe_duration(voice)
    if dur < 3:
        raise SystemExit(f"voice too short ({dur:.2f}s)")

    # Choose visual input: visuals.mp4 > bg.mp4 > plain color
    if visuals.exists():
        v_input = str(visuals)
    elif bg.exists():
        v_input = str(bg)
    else:
        v_input = "lavfi:color=size=1080x1920:rate=30:color=black"

    # Load texts
    overlay = overlay_txt.read_text(encoding="utf-8").strip() if overlay_txt.exists() else ""
    title   = title_txt.read_text(encoding="utf-8").strip()   if title_txt.exists()   else "Daily Episode"

    # Optional music under assets/music/*
    music_dir = Path("assets") / "music"
    music_glob = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    music = random.choice(music_glob) if music_glob else None

    tmp_mp4 = final_dir / f"{ep_dir.name}.nosubs.mp4"
    out_mp4 = final_dir / f"{ep_dir.name}.mp4"

    # Write drawtext via textfile to avoid escaping issues
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        title_file   = td / "title.txt"
        overlay_file = td / "overlay.txt"
        title_file.write_text(title, encoding="utf-8")
        overlay_file.write_text(overlay, encoding="utf-8")

        draw = (
            "format=yuv420p,scale=1080:1920,"
            "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"textfile='{title_file}':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=120,"
            "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"textfile='{overlay_file}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h-300"
        )

        if music:
            # Inputs: 0=v (visuals/bg), 1=voice (mono), 2=music
            filter_complex = (
                f"[0:v]{draw}[vbg];"
                f"[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0[a_voice];"
                f"[2:a]aresample=48000,volume=0.5,sidechaincompress=threshold=0.03:"
                f"ratio=8:attack=5:release=200:makeup=1:scn=1[a_mduck];"
                f"[a_voice][a_mduck]amix=inputs=2:duration=first:dropout_transition=0,volume=1.0[aout]"
            )
            inputs = ["-i", v_input, "-i", str(voice), "-i", str(music)]
        else:
            # Inputs: 0=v (visuals/bg), 1=voice (mono)
            filter_complex = (
                f"[0:v]{draw}[vbg];"
                f"[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0[aout]"
            )
            inputs = ["-i", v_input, "-i", str(voice)]

        # 1) Compose picture+audio (no subs yet)
        cmd1 = [
            FFMPEG, "-y",
            *inputs,
            "-t", f"{dur:.3f}",
            "-filter_complex", filter_complex,
            "-map", "[vbg]", "-map", "[aout]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-profile:v", "baseline", "-level", "4.0",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(tmp_mp4)
        ]
        sh(cmd1)

        # 2) Burn subtitles if present (separate pass keeps filter graphs simple)
        if srt.exists():
            cmd2 = [
                FFMPEG, "-y",
                "-i", str(tmp_mp4),
                "-vf", f"subtitles={srt}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(out_mp4)
            ]
            sh(cmd2)
            try:
                tmp_mp4.unlink()
            except FileNotFoundError:
                pass
        else:
            out_mp4 = tmp_mp4

        # Save path in plan
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["video_path"] = str(out_mp4)
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"[assembly] wrote {out_mp4} (dur≈{dur:.2f}s)")

if __name__ == "__main__":
    main()
