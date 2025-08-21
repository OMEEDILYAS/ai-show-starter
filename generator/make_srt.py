# generator/make_srt.py
import argparse, os, sys
from pathlib import Path

# Uses OpenAI Whisper to create *timed* SRT directly from voice.wav.
# Falls back to heuristic SRT if API fails (so CI still completes).

def heuristic_srt(narration_path: Path, dur: float) -> str:
    # simple fallback: ~2.2 WPS, 7 words per line
    import math
    def fmt_ts(t):
        h=int(t//3600); t-=h*3600; m=int(t//60); t-=m*60; s=int(t); ms=int((t-s)*1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    txt = " ".join(narration_path.read_text(encoding="utf-8").split())
    words = txt.split()
    wps = 2.2; chunk = 7
    srt_lines = []
    idx=1; t=0.0
    for i in range(0, len(words), chunk):
        piece = " ".join(words[i:i+chunk])
        seg = max(len(piece.split())/wps, 0.8)
        start=t; end=min(t+seg, max(dur-0.05, t+0.01))
        if end <= start: break
        srt_lines.append(f"{idx}\n{fmt_ts(start)} --> {fmt_ts(end)}\n{piece}\n")
        idx+=1; t=end
    return "\n".join(srt_lines)

def ffprobe_duration(path: Path) -> float:
    import subprocess
    out = subprocess.check_output([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1", str(path)
    ], text=True).strip()
    try: return float(out)
    except: return 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    series_dir = Path("out")/args.series
    plan_path = sorted(series_dir.glob("ep_*/plan.json"))[-1]
    ep_dir = plan_path.parent
    assets = ep_dir/"assets"
    voice = assets/"voice.wav"
    narration_txt = assets/"narration.txt"
    srt_path = assets/"subtitles.srt"

    if not voice.exists():
        raise SystemExit("voice.wav missing")
    dur = ffprobe_duration(voice)

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            with open(voice, "rb") as f:
                # Whisper with SRT output (aligned timestamps)
                srt = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="srt",
                    temperature=0.0,
                )
            # Some SDKs return bytes/string under .text; handle both
            srt_text = getattr(srt, "text", None) or str(srt)
            if srt_text.strip():
                srt_path.write_text(srt_text, encoding="utf-8")
                print(f"[srt] wrote {srt_path} via Whisper")
                return
        except Exception as e:
            sys.stderr.write(f"[srt] Whisper failed, falling back. Error: {e}\n")

    # Fallback heuristic if no API key or Whisper failed
    if narration_txt.exists():
        srt_text = heuristic_srt(narration_txt, dur)
        srt_path.write_text(srt_text, encoding="utf-8")
        print(f"[srt] wrote {srt_path} (heuristic)")
    else:
        raise SystemExit("narration.txt missing and Whisper unavailable")

if __name__ == "__main__":
    main()
