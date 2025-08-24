# generator/route_shots.py  (WB2 – stock-aware version)
from __future__ import annotations
import argparse, json, os, sys, tempfile, subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Local adapters - handle missing adapters gracefully
slide_adapter = None
diagram_adapter = None
card_adapter = None

try:
    from adapters import slide as slide_adapter
except ImportError:
    pass

try:
    from adapters import diagram as diagram_adapter  
except ImportError:
    pass

try:
    from adapters import card as card_adapter
except ImportError:
    pass

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

def _sh(cmd: List[str]) -> None:
    subprocess.run(cmd, check=True)

def _load_shotlist(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Handle different shotlist formats
    if isinstance(data, list):
        # If it's already a list, check if items are dicts or strings
        if data and isinstance(data[0], str):
            # Convert strings to beat dictionaries
            beats = []
            for i, text in enumerate(data):
                beats.append({
                    "text": text,
                    "keywords": [],
                    "title": f"Beat {i+1}",
                    "duration": 5.0
                })
            return beats
        else:
            return data
    elif isinstance(data, dict):
        # If it's a dict, look for 'beats' key
        if "beats" in data:
            return data["beats"]
        else:
            # Convert single dict to list
            return [data]
    else:
        # Fallback: create a single beat
        return [{"text": str(data), "keywords": [], "title": "Single Beat", "duration": 5.0}]

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _has_bg(bg_path: Path) -> bool:
    return bg_path.exists() and bg_path.stat().st_size > 0

def _series_dirs(series: str, episode: str) -> Dict[str, Path]:
    base = Path("out") / series / episode / "assets"
    return {
        "assets": base,
        "bg": base / "bg.mp4",
        "voice": base / "voice.wav",
        "shots": base / "shots",
        "visuals": base / "visuals.mp4",
        "shotlist": base / "shotlist.json",
        "stock": Path("assets") / "stock" / series,
    }

def _match_stock(stock_dir: Path, keywords: List[str]) -> Optional[Path]:
    """
    Return a stock clip whose filename contains any keyword (case-insensitive).
    If multiple match, prefer the one matching the most tokens. If none, None.
    """
    if not stock_dir.exists():
        return None
    files = sorted(p for p in stock_dir.glob("*.mp4") if p.is_file())
    if not files:
        return None
    kws = [k.lower() for k in keywords if isinstance(k, str)]
    scored: List[Tuple[int, Path]] = []
    for p in files:
        name = p.stem.lower()
        score = sum(1 for k in kws if k and k in name)
        scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].name))
    best_score, best_path = scored[0]
    return best_path if best_score > 0 else None

def _pick_adapter_for_beat(
    force_card: bool,
    stock_dir: Path,
    keywords: List[str],
) -> Tuple[str, Optional[Path]]:
    """
    Decide which adapter to use for a beat.
      - FORCE_CARD => ("card", maybe_stock)
      - If matching stock => ("card", stock_path)
      - Heuristics for diagram/slide
    Returns (adapter_name, stock_path_if_any)
    """
    if force_card:
        sp = _match_stock(stock_dir, keywords)
        return ("card", sp)

    sp = _match_stock(stock_dir, keywords)
    if sp is not None:
        return ("card", sp)

    kw = " ".join(k.lower() for k in keywords if isinstance(k, str))
    if any(t in kw for t in ("diagram", "flow", "map", "axes", "vector", "matrix", "plot")):
        return ("diagram", None)

    return ("slide", None)

def _concat_shots_to_visuals(shots: List[Path], visuals_path: Path) -> None:
    if not shots:
        raise RuntimeError("No shots to concat.")
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".txt") as f:
        for p in shots:
            f.write(f"file '{p.absolute()}'\n")
        list_path = Path(f.name)
    try:
        cmd = [
            FFMPEG, "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-c", "copy",
            str(visuals_path),
        ]
        _sh(cmd)
    finally:
        # Clean up temp file
        try:
            list_path.unlink()
        except Exception:
            pass

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--episode", default="ep_001")
    args = ap.parse_args()

    dirs = _series_dirs(args.series, args.episode)
    shotlist_path = dirs["shotlist"]
    bg_path = dirs["bg"]
    shots_dir = dirs["shots"]
    visuals = dirs["visuals"]
    stock_dir = dirs["stock"]

    if not shotlist_path.exists():
        print(f"[router] ERROR: missing shotlist {shotlist_path}")
        return 1

    _ensure_dir(shots_dir)

    beats = _load_shotlist(shotlist_path)
    force_card = os.environ.get("FORCE_CARD", "") == "1"

    print(f"[router] beats: {len(beats)}  series={args.series}  ep={args.episode}")
    if not _has_bg(bg_path):
        print(f"[router] WARN: bg not found at {bg_path}, adapters will still draw but visuals may feel flat.")

    made: List[Path] = []

    for i, beat in enumerate(beats):
        text = beat.get("text") or ""
        keywords = beat.get("keywords") or []
        title = beat.get("title") or ""  # optional field if present

        adapter_name, stock_path = _pick_adapter_for_beat(force_card, stock_dir, keywords)
        out = shots_dir / f"{i:03d}.mp4"

        # Execute adapter
        try:
            if adapter_name == "card" and card_adapter and hasattr(card_adapter, 'render'):
                # Card adapter uses the correct signature already
                card_adapter.render(
                    bg_path=bg_path,
                    out_path=out,
                    title=(title or " "),
                    text=text,
                    keywords=keywords,
                    stock_dir=stock_dir,
                    duration=beat.get("duration", 5.9),
                )
            elif adapter_name == "diagram" and diagram_adapter and hasattr(diagram_adapter, 'make'):
                # Diagram adapter uses different signature
                beat_dict = {
                    "keywords": keywords,
                    "text": text,
                    "title": title,
                    "dur": beat.get("duration", 5.9)
                }
                diagram_adapter.make(beat_dict, i, shots_dir.parent.parent)
            elif adapter_name == "slide" and slide_adapter and hasattr(slide_adapter, 'make'):
                # Slide adapter uses different signature  
                beat_dict = {
                    "title": title,
                    "text": text,
                    "keywords": keywords,
                    "dur": beat.get("duration", 5.9)
                }
                slide_adapter.make(beat_dict, i, shots_dir.parent.parent)
            else:
                # Fallback: copy a short chunk of bg.mp4 so pipeline doesn't break
                if bg_path.exists():
                    cmd = [
                        FFMPEG, "-y",
                        "-i", str(bg_path),
                        "-t", "4.9",
                        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(out),
                    ]
                    _sh(cmd)
                else:
                    # Absolute fallback - solid color
                    cmd = [
                        FFMPEG, "-y",
                        "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=4.9",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(out),
                    ]
                    _sh(cmd)

        except Exception as e:
            print(f"[router] ERROR beat {i} ({adapter_name}): {e}")
            # create a tiny safe fallback so concatenation still works
            try:
                cmd = [
                    FFMPEG, "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=4.9",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(out),
                ]
                _sh(cmd)
            except Exception as e2:
                print(f"[router] ABORT beat {i}: fallback failed: {e2}")
                return 1

        # Unified log line you asked for:
        t = adapter_name
        adapter_used = t if t in ("slide", "diagram", "math", "map", "code") else "stock"
        kws = [k for k in keywords if isinstance(k, str)]
        print(f"[router] beat {i}: used {adapter_used.upper()} for keywords {kws} -> {out}")

        made.append(out)

    # Concat all shots
    if made:
        print("[router] shots:")
        for p in made:
            print(f"  - {p}")
        _concat_shots_to_visuals(made, visuals)
        print(f"[router] wrote {visuals}")
    else:
        print("[router] ERROR: no shots were made.")
        return 2

    return 0

if __name__ == "__main__":
    sys.exit(main())