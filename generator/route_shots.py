#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Route beats from the shotlist to visual adapters and stitch them into visuals.mp4.
- Expects shotlist at out/<series>/<ep>/assets/shotlist.json
- Writes per-beat shots to out/<series>/<ep>/assets/shots/NNN.mp4
- Concats shots into out/<series>/<ep>/assets/visuals.mp4
"""

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple

# ----------------------------
# Adapter imports (repo layout: AI-SHOW-STARTER/adapters/*)
# ----------------------------
try:
    from adapters.slide_cards import make_slide
except Exception:
    make_slide = None

try:
    from adapters.diagram_basic import make_diagram
except Exception:
    make_diagram = None

try:
    from adapters.stock_snippets import make_stock_snip
except Exception:
    make_stock_snip = None

try:
    # the "cards" visual adapter that assembles stock + text into a card-style vertical clip
    from adapters.card import render as card_render
except Exception:
    card_render = None


# ----------------------------
# Utils
# ----------------------------

def sh(cmd: List[str], check=True) -> Tuple[int, str]:
    """Run a shell command and return (exit_code, combined_output)."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out, _ = proc.communicate()
    if check and proc.returncode != 0:
        print(out)
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc.returncode, out or ""


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def load_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_concat_list(paths: List[Path]) -> Path:
    # ffmpeg concat demuxer file
    tmp = Path("/tmp") / f"concat_{os.getpid()}.txt"
    with tmp.open("w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{p.as_posix()}'\n")
    return tmp


def transcode_copy_concat(inputs: List[Path], out_path: Path):
    concat_file = write_concat_list(inputs)
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file.as_posix(),
        "-c", "copy",
        out_path.as_posix()
    ]
    sh(cmd)
    try:
        concat_file.unlink(missing_ok=True)
    except Exception:
        pass


def reencode_to_v(h264_in: Path, out_path: Path, w=1080, h=1920, fps=30):
    cmd = [
        "ffmpeg", "-y",
        "-i", h264_in.as_posix(),
        "-r", str(fps),
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-level:v", "4.0",
        "-preset", "veryfast",
        out_path.as_posix()
    ]
    sh(cmd)


# ----------------------------
# Adapter routing
# ----------------------------

def choose_adapter_tag(beat: Dict[str, Any]) -> str:
    """
    Decide which adapter tag to use. We honor explicit beat['type'] if present,
    otherwise fall back to keywords.
    """
    t = (beat.get("type") or "").strip().lower()
    if t in ("slide", "diagram", "math", "map", "code", "stock", "card"):
        return t

    # heuristic by keywords if no explicit type
    kws = " ".join(beat.get("keywords") or [])
    if any(k in kws.lower() for k in ("diagram", "chart", "plot", "flow")):
        return "diagram"
    if any(k in kws.lower() for k in ("map", "coordinates")):
        return "map"
    if any(k in kws.lower() for k in ("equation", "math", "formula")):
        return "math"
    if any(k in kws.lower() for k in ("code", "snippet")):
        return "code"
    if any(k in kws.lower() for k in ("stock", "b-roll", "broll", "footage", "video")):
        return "stock"
    # default to slide/card style
    return "slide"


def render_with_adapter(tag: str,
                        beat: Dict[str, Any],
                        work: Dict[str, Path]) -> Path:
    """
    Dispatch to the right adapter. Adapters should return a path to an MP4 (1080x1920).
    """
    series = work["series"]
    ep_dir = work["ep_dir"]
    assets_dir = work["assets_dir"]
    stock_dir = work["stock_dir"]
    tmp_dir = work["tmp_dir"]

    text = (beat.get("text") or "").strip()
    kws = beat.get("keywords") or []
    hint = (beat.get("hint") or "").strip()

    # Normalize tag
    t = (tag or "").lower()

    # 1) Card adapter (preferred for quick visuals that combine text + stock)
    if t == "card" and card_render:
        return Path(card_render(
            text=text,
            keywords=kws,
            stock_dir=stock_dir.as_posix(),
            out_dir=tmp_dir.as_posix(),
            title=beat.get("title") or "",
            subtitle=beat.get("subtitle") or "",
        ))

    # 2) Slide
    if t == "slide" and make_slide:
        return Path(make_slide(
            text=text,
            keywords=kws,
            out_dir=tmp_dir.as_posix(),
            title=beat.get("title") or "",
            subtitle=beat.get("subtitle") or "",
        ))

    # 3) Diagram
    if t == "diagram" and make_diagram:
        return Path(make_diagram(
            text=text,
            keywords=kws,
            out_dir=tmp_dir.as_posix(),
            style=beat.get("style") or "chalk",
        ))

    # 4) Stock snippet
    if t == "stock" and make_stock_snip:
        return Path(make_stock_snip(
            keywords=kws,
            stock_dir=stock_dir.as_posix(),
            out_dir=tmp_dir.as_posix(),
            duration=float(beat.get("duration") or 5.0),
        ))

    # 5) If they asked for slide/diagram/math/map/code but adapter missing, fall back to card if available
    if card_render:
        return Path(card_render(
            text=text,
            keywords=kws,
            stock_dir=stock_dir.as_posix(),
            out_dir=tmp_dir.as_posix(),
            title=beat.get("title") or "",
            subtitle=beat.get("subtitle") or "",
        ))

    # 6) Absolute last resort: reuse bg as a placeholder clip (to avoid pipeline failure)
    bg = assets_dir / "bg.mp4"
    placeholder = tmp_dir / "placeholder.mp4"
    reencode_to_v(bg, placeholder)
    return placeholder


# ----------------------------
# Main
# ----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True, help="Series key, e.g., ai_teacher")
    ap.add_argument("--episode", default="ep_001", help="Episode folder, default ep_001")
    args = ap.parse_args()

    root = Path.cwd()
    series = args.series
    ep = args.episode

    ep_dir = root / "out" / series / ep
    assets_dir = ep_dir / "assets"
    shots_dir = assets_dir / "shots"
    ensure_dir(shots_dir)

    tmp_dir = ep_dir / "tmp_route"
    ensure_dir(tmp_dir)

    shotlist_path = assets_dir / "shotlist.json"
    if not shotlist_path.exists():
        print(f"[router] ERROR: missing shotlist {shotlist_path}")
        sys.exit(1)

    stock_dir = (root / "assets" / "stock" / series)
    ensure_dir(stock_dir)  # ok if empty; card/stock adapters handle empties gracefully

    beats = load_json(shotlist_path)
    if isinstance(beats, dict) and "beats" in beats:
        beats = beats["beats"]
    if not isinstance(beats, list):
        print("[router] ERROR: shotlist must be a list or dict with 'beats'")
        sys.exit(1)

    made: List[Path] = []

    for i, beat in enumerate(beats):
        # Decide adapter
        chosen = choose_adapter_tag(beat)
        kws = beat.get("keywords") or []

        # For now: nudge slide/diagram beats to "card" to guarantee visuals with stock
        # (You can remove this if you want the original adapters directly.)
        preferred = chosen
        if chosen in ("slide", "diagram") and card_render:
            preferred = "card"

        # Render
        try:
            out_clip = render_with_adapter(preferred, beat, {
                "series": series,
                "ep_dir": ep_dir,
                "assets_dir": assets_dir,
                "stock_dir": stock_dir,
                "tmp_dir": tmp_dir,
            })
        except Exception as e:
            print(f"[router] beat {i}: ERROR rendering with {preferred}: {e}")
            # fallback to bg placeholder
            bg = assets_dir / "bg.mp4"
            out_clip = tmp_dir / f"fallback_{i:03d}.mp4"
            reencode_to_v(bg, out_clip)

        # Transcode to vertical spec & drop into shots/
        shot_path = shots_dir / f"{i:03d}.mp4"
        try:
            reencode_to_v(out_clip, shot_path, w=1080, h=1920, fps=30)
        except Exception as e:
            print(f"[router] beat {i}: ERROR transcoding: {e}")
            # fallback again to bg to keep pipeline going
            bg = assets_dir / "bg.mp4"
            reencode_to_v(bg, shot_path, w=1080, h=1920, fps=30)

        # Log which adapter we effectively used (after generating each beat, before appending)
        t = preferred
        adapter_used = t if t in ("slide", "diagram", "math", "map", "code", "stock", "card") else "stock"
        print(f"[router] beat {i}: used {adapter_used.upper()} for keywords {kws} -> {shot_path}")

        made.append(shot_path)

    if not made:
        print("[router] nothing generated; aborting.")
        sys.exit(1)

    print("[router] shots:")
    for p in made:
        print(f"  - {p.as_posix()}")

    visuals = assets_dir / "visuals.mp4"
    # Concat without re-encode for speed (we re-encoded shots uniformly above)
    transcode_copy_concat(made, visuals)

    print(f"[router] wrote {visuals.as_posix()}")


if __name__ == "__main__":
    main()
