# generator/route_shots.py  (WB3 – stock-first + card-forward version)
from __future__ import annotations
import argparse, json, os, sys, tempfile, subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --- Optional adapters (import gracefully) ---
card_adapter = None
slide_cards_adapter = None
diagram_basic_adapter = None

try:
    # adapters/card.py
    from adapters import card as card_adapter
except ImportError:
    pass

try:
    # adapters/slide_cards.py  -> make_slide(text, out_path, dur, title="")
    from adapters import slide_cards as slide_cards_adapter
except ImportError:
    pass

try:
    # adapters/diagram_basic.py -> make_diagram(text, keywords, out_path, dur)
    from adapters import diagram_basic as diagram_basic_adapter
except ImportError:
    pass

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

def _sh(cmd: List[str]) -> None:
    subprocess.run(cmd, check=True)

def _load_shotlist(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        if data and isinstance(data[0], str):
            # Convert simple string list -> beat dicts
            beats = []
            for i, text in enumerate(data):
                beats.append({
                    "text": text,
                    "keywords": [],
                    "title": f"Beat {i+1}",
                    "duration": 5.0
                })
            return beats
        return data
    elif isinstance(data, dict):
        return data.get("beats") or [data]
    else:
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
        "stock_list": base / "stock_list.txt",
    }

# ---------- Stock selection helpers ----------
def _read_stock_list(stock_list_path: Path) -> List[Path]:
    """Prefer clips scored/selected by select_stock.py -> assets/stock_list.txt"""
    if not stock_list_path.exists():
        return []
    lines = [ln.strip() for ln in stock_list_path.read_text(encoding="utf-8").splitlines()]
    paths = [Path(ln) for ln in lines if ln]
    return [p for p in paths if p.exists() and p.is_file()]

def _keyword_score(name: str, keywords: List[str]) -> int:
    n = name.lower()
    kws = [k.lower() for k in keywords if isinstance(k, str)]
    return sum(1 for k in kws if k and k in n)

def _match_from_candidates(cands: List[Path], keywords: List[str]) -> Optional[Path]:
    if not cands:
        return None
    scored = [(_keyword_score(p.stem, keywords), p) for p in cands]
    scored.sort(key=lambda x: (-x[0], x[1].name))
    best_score, best = scored[0]
    return best if best_score > 0 else cands[0]  # fall back to first if no hits

def _match_stock(stock_dir: Path, stock_list_path: Path, keywords: List[str]) -> Optional[Path]:
    """
    Choose a stock clip with priorities:
      1) anything listed in assets/stock_list.txt (pre-scored by select_stock.py), best keyword match
      2) any clip under assets/stock/<series> by filename keyword match
    """
    # 1) Prefer pre-picked list
    preferred = _read_stock_list(stock_list_path)
    choice = _match_from_candidates(preferred, keywords)
    if choice:
        return choice

    # 2) Fall back to series library
    if stock_dir.exists():
        library = sorted(p for p in stock_dir.glob("*.mp4") if p.is_file())
        if library:
            return _match_from_candidates(library, keywords)
    return None

# ---------- Adapter selection ----------
def _pick_adapter_for_beat(force_card: bool, stock_dir: Path, stock_list_path: Path, keywords: List[str]) -> Tuple[str, Optional[Path]]:
    """
    Decide which adapter to use for a beat.
      - If FORCE_CARD=1 => 'card' (try to attach stock)
      - Else if any stock match => 'card' (with that stock)
      - Else simple heuristics for diagram vs slide
    """
    if force_card:
        sp = _match_stock(stock_dir, stock_list_path, keywords)
        return ("card", sp)

    sp = _match_stock(stock_dir, stock_list_path, keywords)
    if sp is not None:
        return ("card", sp)

    kw = " ".join(k.lower() for k in keywords if isinstance(k, str))
    if any(t in kw for t in ("diagram", "flow", "map", "axes", "vector", "matrix", "plot", "chart", "graph")):
        return ("diagram", None)

    return ("slide", None)

# ---------- Concat ----------
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
        try:
            list_path.unlink()
        except Exception:
            pass

# ---------- Main ----------
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
    stock_list_path = dirs["stock_list"]

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
        text = (beat.get("text") or "").strip()
        keywords = beat.get("keywords") or []
        title = (beat.get("title") or "").strip()
        dur = float(beat.get("duration", beat.get("dur", 5.9)) or 5.9)

        adapter_name, stock_path = _pick_adapter_for_beat(force_card, stock_dir, stock_list_path, keywords)
        out = shots_dir / f"{i:03d}.mp4"

        try:
            if adapter_name == "card" and card_adapter and hasattr(card_adapter, "render"):
                # Card with stock video panel when available
                card_adapter.render(
                    bg_path=bg_path,
                    out_path=out,
                    title=(title or " "),
                    text=text,
                    keywords=keywords,
                    stock_dir=stock_dir,  # card adapter will pick stock internally; our picker nudges via filenames/stock_list
                    duration=dur,
                )

            elif adapter_name == "diagram" and diagram_basic_adapter and hasattr(diagram_basic_adapter, "make_diagram"):
                # Clean diagram style (header bar + caption)
                diagram_basic_adapter.make_diagram(text=text or title or "Diagram", keywords=keywords, out=out, dur=dur)

            elif adapter_name == "slide" and slide_cards_adapter and hasattr(slide_cards_adapter, "make_slide"):
                # Centered, readable slide with optional title
                slide_cards_adapter.make_slide(text=text or title or "Slide", out=out, dur=dur, title=title)

            else:
                # Fallback: if we have a bg, take a short slice; else solid color
                if bg_path.exists():
                    cmd = [
                        FFMPEG, "-y",
                        "-i", str(bg_path),
                        "-t", f"{min(max(dur,1.5),15.0):.2f}",
                        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(out),
                    ]
                    _sh(cmd)
                else:
                    cmd = [
                        FFMPEG, "-y",
                        "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={min(max(dur,1.5),15.0):.2f}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(out),
                    ]
                    _sh(cmd)

        except Exception as e:
            print(f"[router] ERROR beat {i} ({adapter_name}): {e}")
            # safe fallback frame so concat still works
            try:
                cmd = [
                    FFMPEG, "-y",
                    "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={min(max(dur,1.5),15.0):.2f}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(out),
                ]
                _sh(cmd)
            except Exception as e2:
                print(f"[router] ABORT beat {i}: fallback failed: {e2}")
                return 1

        # Log
        used = adapter_name.upper()
        print(f"[router] beat {i}: used {used}  keywords={keywords}  -> {out}")

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
