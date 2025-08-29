#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generator/gen_background.py (WB3 – robust)
Purpose:
  - Create a vertical background video (bg.mp4) for the current episode.
  - DO NOT fail the pipeline if the TTS voice is short or missing.
    Instead, synthesize a background of a reasonable duration so later
    stages (visuals, assembly) can still run.

Behavior:
  - Looks for latest out/<series>/ep_*/assets/.
  - Measures assets/voice.wav duration.
  - If duration < 4.0s, we WARN (do not error) and choose a safe bg duration:
      * If narration.txt exists, estimate duration from words (≈ 80–90s target).
      * Otherwise use a default (e.g., 60s).
  - Generates bg.mp4 using ffmpeg color source.
  - Exits 0 always.

Requires:
  - ffmpeg installed (workflow already has it)
Env:
  - BG_COLOR (hex like 0x101426), optional.
"""

import argparse
import os
import subprocess
import wave
from contextlib import closing
from pathlib import Path

DEFAULT_BG_HEX = os.environ.get("BG_COLOR", "0x101426")  # same default as before
SIZE = "1080x1920"

def _latest_assets(series: str) -> Path:
    root = Path("out") / series
    eps = sorted(root.glob("ep_*"))
    if not eps:
        raise FileNotFoundError(f"No episodes under {root}/ep_*")
    return eps[-1] / "assets"

def _wav_duration_s(p: Path) -> float:
    if not p.exists():
        return 0.0
    try:
        with closing(wave.open(str(p), "rb")) as w:
            frames = w.getnframes()
            rate = w.getframerate()
            return frames / float(rate or 1)
    except Exception:
        return 0.0

def _word_count(p: Path) -> int:
    try:
        txt = p.read_text(encoding="utf-8")
        return len(txt.strip().split())
    except Exception:
        return 0

def _estimate_from_words(words: int) -> float:
    # Slow, clear pace ~ 120–140 wpm → 70–90 seconds for 150–190 words
    if words <= 0:
        return 60.0
    # map 100–220 words to ~55–100s
    est = max(40.0, min(100.0, words * 0.5))
    return est

def _make_bg(out_mp4: Path, seconds: float, color_hex: str = DEFAULT_BG_HEX) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    # Simple solid color; yuv420p for IG compatibility. You can add subtle noise/vignette later.
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={color_hex}:s={SIZE}:d={seconds:.2f}",
        "-vf", "format=yuv420p",
        str(out_mp4)
    ]
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True, help="Series slug (math_of_ML | MAS | mixed)")
    args = ap.parse_args()

    try:
        assets = _latest_assets(args.series)
    except Exception as e:
        # If there is truly no episode, just exit 0 so the matrix job for this series doesn't kill the workflow.
        print(f"[bg] WARN: {e}")
        return 0

    voice = assets / "voice.wav"
    narration = assets / "narration.txt"
    bg = assets / "bg.mp4"

    dur = _wav_duration_s(voice)
    if dur < 4.0:
        # Don't fail. Pick a sane background length.
        wc = _word_count(narration)
        est = _estimate_from_words(wc)
        print(f"[bg] WARN: voice too short ({dur:.2f}s). words={wc} → est_bg={est:.1f}s")
        dur_bg = est
    else:
        # Give a bit of buffer beyond the voice so visuals have room
        dur_bg = max(dur + 2.0, 12.0)

    try:
        _make_bg(bg, dur_bg, DEFAULT_BG_HEX)
        print(f"[bg] OK: wrote {bg} ({dur_bg:.1f}s)")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"[bg] ERROR: ffmpeg failed: {e}")
        # As a last resort, try a small 12s background
        try:
            _make_bg(bg, 12.0, DEFAULT_BG_HEX)
            print(f"[bg] OK (fallback 12s): {bg}")
            return 0
        except Exception as e2:
            print(f"[bg] FATAL: {e2}")
            # still exit 0 to avoid killing the run; downstream can add its own guard
            return 0

if __name__ == "__main__":
    raise SystemExit(main())
