#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generator/gen_background.py (WB3 hardened)
Goal:
  - Generate a vertical bg video (assets/bg.mp4) with a sane duration.
  - Never create multi-hour videos; clamp to 50–95 seconds.
  - If TTS is short/missing, estimate from narration words; still clamp.
  - Never kill the pipeline on background issues.

Inputs (per latest episode):
  out/<series>/ep_*/assets/narration.txt   (optional, for word-based estimate)
  out/<series>/ep_*/assets/voice.wav       (optional, for voice duration)

Outputs:
  out/<series>/ep_*/assets/bg.mp4

Env:
  BG_COLOR hex (e.g., 0x101426). Optional.
"""

import argparse
import os
import subprocess
import wave
from contextlib import closing
from pathlib import Path

# -------- constants & helpers --------
DEFAULT_BG_HEX = os.environ.get("BG_COLOR", "0x101426")
SIZE = "1080x1920"
MIN_S = 50.0         # we target IG reels ~70–90s; never shorter than 50s
MAX_S = 95.0         # never longer than 95s
SAFETY_PAD = 2.0     # add on top of voice duration

def _latest_assets(series: str) -> Path:
    base = Path("out") / series
    eps = sorted(base.glob("ep_*"))
    if not eps:
        raise FileNotFoundError(f"No episodes under {base}/")
    return eps[-1] / "assets"

def _wav_duration_s(path: Path) -> float:
    if not path.exists():
        return 0.0
    try:
        with closing(wave.open(str(path), "rb")) as w:
            frames = w.getnframes()
            rate = w.getframerate() or 1
            return frames / float(rate)
    except Exception:
        return 0.0

def _word_count(path: Path) -> int:
    try:
        txt = path.read_text(encoding="utf-8")
        return len(txt.split())
    except Exception:
        return 0

def _estimate_from_words(words: int) -> float:
    # ~135 wpm → ≈ 0.44s per word. Clamp to [MIN_S, MAX_S] later.
    if words <= 0:
        return 60.0
    return words * 0.44

def _clamp(seconds: float) -> float:
    # Hard guard to stop any runaway hours-long encodes
    return max(MIN_S, min(MAX_S, float(seconds)))

def _make_bg(out_mp4: Path, seconds: float, color_hex: str) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    # Use lavfi color source; stream-copy is not possible here (we synthesize fresh)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        f"-i", f"color=c={color_hex}:s={SIZE}:d={seconds:.2f}",
        "-vf", "format=yuv420p",
        "-r", "25",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out_mp4)
    ]
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True, help="Series slug (e.g., math_of_ML | MAS | mixed)")
    args = ap.parse_args()

    try:
        assets = _latest_assets(args.series)
    except Exception as e:
        print(f"[bg] WARN: {e}")
        return 0

    voice = assets / "voice.wav"
    narration = assets / "narration.txt"
    out_bg = assets / "bg.mp4"

    # 1) try voice length
    voice_s = _wav_duration_s(voice)

    # 2) fallback: estimate from narration words
    words = _word_count(narration)
    est_s = _estimate_from_words(words) if voice_s < 4.0 else voice_s + SAFETY_PAD

    # 3) clamp aggressively to 50–95 seconds
    final_s = _clamp(est_s)

    print(f"[bg] voice={voice_s:.2f}s words={words} est={est_s:.2f}s → clamped={final_s:.2f}s")

    try:
        _make_bg(out_bg, final_s, DEFAULT_BG_HEX)
        print(f"[bg] OK: wrote {out_bg} ({final_s:.2f}s)")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"[bg] ERROR: ffmpeg failed: {e}. Trying 60s fallback.")
        try:
            _make_bg(out_bg, _clamp(60.0), DEFAULT_BG_HEX)
            print(f"[bg] OK: fallback wrote {out_bg} (60.00s)")
            return 0
        except Exception as e2:
            print(f"[bg] FATAL: {e2} (giving up but not failing step)")
            return 0

if __name__ == "__main__":
    raise SystemExit(main())
