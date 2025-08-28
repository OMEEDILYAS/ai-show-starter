#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Route beats to topic adapters (NO stock footage).
- Linear Algebra → adapters/la_viz.py
- Multi-Agent Systems → adapters/mas_viz.py
- Fallbacks → adapters/diagram_flow.py / adapters/chart_simple.py

This script reads the latest episode's shotlist.json and creates
1080x1920 shots per beat, then concatenates to visuals.mp4.

ENV
  PYTHONPATH should include repo root so adapters import cleanly.
"""
from __future__ import annotations
import argparse, json, os, subprocess, tempfile
from pathlib import Path
from typing import Dict, List

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

# Adapters: try package then top-level
def _import_adapter(modname: str):
    try:
        return __import__(f"adapters.{modname}", fromlist=["*"])
    except Exception:
        return __import__(modname)

def _load_shotlist(p: Path) -> List[Dict]:
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "beats" in data: return data["beats"]
    if isinstance(data, list): return data
    return [{"text": str(data), "keywords": [], "title": "Beat", "duration": 6.0}]

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _concat(shots: List[Path], out_path: Path) -> None:
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".txt") as f:
        for s in shots:
            f.write(f"file '{s.absolute()}'\n")
        lst = Path(f.name)
    try:
        subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "copy", str(out_path)], check=True)
    finally:
        try: lst.unlink()
        except Exception: pass

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--episode", default=None)
    args = ap.parse_args()

    series = args.series
    series_dir = Path("out") / series
    plans = sorted(series_dir.glob("ep_*/plan.json"))
    if not plans:
        print(f"[router] ERROR: no plan.json under {series_dir}/ep_*/")
        return 1
    plan_path = plans[-1]
    ep_dir = plan_path.parent
    assets = ep_dir / "assets"
    shots_dir = assets / "shots"
    visuals = assets / "visuals.mp4"
    bg = assets / "bg.mp4"
    shotlist = assets / "shotlist.json"

    _ensure_dir(shots_dir)
    beats = _load_shotlist(shotlist)

    # pick adapter set based on series/topic
    is_math = series in ("math_of_ML", "ai_teacher", "ai_teacher_linear_algebra")
    is_mas  = series in ("MAS", "ai_teacher_mas")

    la = _import_adapter("la_viz")
    mas = _import_adapter("mas_viz")
    flow = _import_adapter("diagram_flow")
    chart = _import_adapter("chart_simple")

    made: List[Path] = []
    for i, b in enumerate(beats):
        text = (b.get("text") or "").strip()
        title = (b.get("title") or "").strip()
        kws = b.get("keywords") or []
        dur = float(b.get("duration") or 6.0)
        out = shots_dir / f"{i:03d}.mp4"

        try:
            if is_math:
                # Linear algebra visuals first; fallback to chart/flow
                print(f"[router] beat {i}: LA_VIZ d={dur:.1f}s kws={kws[:4]}")
                la.render(text=text or title, out_path=out, duration=dur)
            elif is_mas:
                print(f"[router] beat {i}: MAS_VIZ d={dur:.1f}s kws={kws[:4]}")
                mas.render(text=text or title, out_path=out, duration=dur)
            else:
                # Generic fallbacks
                if i % 2 == 0:
                    print(f"[router] beat {i}: FLOW d={dur:.1f}s")
                    flow.render(text=text or title, out_path=out, duration=dur)
                else:
                    print(f"[router] beat {i}: CHART d={dur:.1f}s")
                    chart.render(text=text or title, out_path=out, duration=dur)
        except Exception as e:
            print(f"[router] ERROR beat {i}: {e} → fallback solid")
            subprocess.run([FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c=0x101426:s=1080x1920:d={dur:.2f}",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)], check=False)

        made.append(out)

    if not made:
        print("[router] ERROR: no shots produced.")
        return 2

    print(f"[router] concat → {visuals}")
    _concat(made, visuals)
    print(f"[router] visuals: {visuals}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
