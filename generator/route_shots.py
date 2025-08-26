# generator/route_shots.py
from __future__ import annotations
import argparse, json, os, sys, tempfile, subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Try adapters package first, then top-level
card_adapter = None
slide_cards_adapter = None
diagram_basic_adapter = None
try:
    from adapters import card as card_adapter
except ImportError:
    try: import card as card_adapter
    except ImportError: pass
try:
    from adapters import slide_cards as slide_cards_adapter
except ImportError:
    try: import slide_cards as slide_cards_adapter
    except ImportError: pass
try:
    from adapters import diagram_basic as diagram_basic_adapter
except ImportError:
    try: import diagram_basic as diagram_basic_adapter
    except ImportError: pass

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

def _sh(cmd: List[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)

def _load_shotlist(path: Path) -> List[Dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict): return data.get("beats") or [data]
    if isinstance(data, list): return data
    return [{"text": str(data), "keywords": [], "title": "Beat", "duration": 5.9}]

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _series_dirs(series: str, episode: str) -> Dict[str, Path]:
    base = Path("out") / series / episode / "assets"
    return {
        "assets": base,
        "bg": base / "bg.mp4",
        "shots": base / "shots",
        "visuals": base / "visuals.mp4",
        "shotlist": base / "shotlist.json",
        "stock": Path("assets") / "stock" / series,  # repo-local stock library
        "stock_list": base / "stock_list.txt",       # created by select_stock.py
    }

def _read_stock_list(stock_list_path: Path) -> List[Path]:
    if not stock_list_path.exists(): return []
    lines = [ln.strip() for ln in stock_list_path.read_text(encoding="utf-8").splitlines()]
    return [Path(ln) for ln in lines if ln]

def _keyword_str(keywords: List[str]) -> str:
    return " ".join(k for k in (keywords or []) if isinstance(k, str))

def _pick_adapter_for_beat(force_card: bool, stock_dir: Path, stock_list_path: Path, keywords: List[str]) -> Tuple[str, Optional[Path]]:
    """
    Decide adapter and return (name, override_clip).
    - If we have a pre-selected list (assets/stock_list.txt), use its first path that exists.
    - Else, no override here; card.py will auto-pick from stock_dir.
    """
    if force_card:
        override = None
        picks = _read_stock_list(stock_list_path)
        for p in picks:
            if p.exists():
                override = p; break
        return ("card", override)

    # Prefer card if stock exists in either place
    if stock_dir.exists() or stock_list_path.exists():
        override = None
        picks = _read_stock_list(stock_list_path)
        for p in picks:
            if p.exists():
                override = p; break
        return ("card", override)

    # Otherwise heuristic between diagram/slide based on keywords
    kw = _keyword_str(keywords).lower()
    if any(t in kw for t in ("diagram","flow","map","axes","vector","matrix","plot","chart","graph")):
        return ("diagram", None)
    return ("slide", None)

def _concat_shots_to_visuals(shots: List[Path], visuals_path: Path) -> None:
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".txt") as f:
        for p in shots:
            f.write(f"file '{p.absolute()}'\n")
        list_path = Path(f.name)
    try:
        _sh([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-c", "copy", str(visuals_path)])
    finally:
        try: list_path.unlink()
        except Exception: pass

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--episode", default=None)
    args = ap.parse_args()

    # Pick latest episode if not provided
    series_dir = Path("out") / args.series
    plans = sorted(series_dir.glob("ep_*/plan.json"))
    if not plans:
        print(f"[router] ERROR: no plan.json in {series_dir}/ep_*/")
        return 1
    plan_path = plans[-1]
    ep_dir = plan_path.parent
    episode = ep_dir.name

    dirs = _series_dirs(args.series, episode)
    shotlist_path = dirs["shotlist"]
    bg_path = dirs["bg"]
    shots_dir = dirs["shots"]
    visuals = dirs["visuals"]
    stock_dir = dirs["stock"]
    stock_list_path = dirs["stock_list"]

    print(f"[router] series={args.series} episode={episode}")
    print(f"[router] stock_dir={stock_dir} exists={stock_dir.exists()}")
    if stock_dir.exists():
        # show a quick count for sanity
        import glob as _glob
        cnt = len(_glob.glob(str(stock_dir / "**/*.[mM][pP]4"), recursive=True)) + len(_glob.glob(str(stock_dir / "**/*.[mM][oO][vV]"), recursive=True))
        print(f"[router] stock candidates under stock_dir: ~{cnt}")

    _ensure_dir(shots_dir)
    beats = _load_shotlist(shotlist_path)
    force_card = os.environ.get("FORCE_CARD", "") == "1"

    made: List[Path] = []
    for i, beat in enumerate(beats):
        text = (beat.get("text") or "").strip()
        keywords = beat.get("keywords") or []
        title = (beat.get("title") or "").strip()
        dur = float(beat.get("duration", beat.get("dur", 5.9)) or 5.9)

        adapter_name, override_clip = _pick_adapter_for_beat(force_card, stock_dir, stock_list_path, keywords)
        out = shots_dir / f"{i:03d}.mp4"

        try:
            if adapter_name == "card" and card_adapter and hasattr(card_adapter, "render"):
                print(f"[router] beat {i}: CARD keywords={keywords} override_clip={override_clip}")
                card_adapter.render(
                    bg_path=bg_path,
                    out_path=out,
                    title=(title or " "),
                    text=text,
                    keywords=keywords,
                    stock_dir=stock_dir,
                    duration=dur,
                    override_clip=override_clip,   # NEW: deterministic stock
                )
            elif adapter_name == "diagram" and diagram_basic_adapter and hasattr(diagram_basic_adapter, "make_diagram"):
                print(f"[router] beat {i}: DIAGRAM keywords={keywords}")
                diagram_basic_adapter.make_diagram(text=text or title or "Diagram", keywords=keywords, out=out, dur=dur)
            elif adapter_name == "slide" and slide_cards_adapter and hasattr(slide_cards_adapter, "make_slide"):
                print(f"[router] beat {i}: SLIDE keywords={keywords}")
                slide_cards_adapter.make_slide(text=text or title or "Slide", out=out, dur=dur, title=title)
            else:
                print(f"[router] beat {i}: FALLBACK (drawing plain bg)")
                _sh([
                    FFMPEG, "-y",
                    "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={min(max(dur,1.5),15.0):.2f}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(out),
                ])

        except Exception as e:
            print(f"[router] ERROR beat {i} ({adapter_name}): {e}")
            _sh([
                FFMPEG, "-y",
                "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={min(max(dur,1.5),15.0):.2f}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(out),
            ])

        made.append(out)

    if not made:
        print("[router] ERROR: no shots were made.")
        return 2

    print("[router] concatenating shots →", visuals)
    _concat_shots_to_visuals(made, visuals)
    print(f"[router] wrote {visuals}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
