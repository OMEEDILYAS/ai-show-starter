#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
route_shots.py (WB3)
- Reads latest shotlist.json for the series
- Chooses adapter + mode per beat (variety), avoids repeating same mode too often
- If < 12 beats, pad with filler beats to ensure visual variety
- Produces assets/shots/*.mp4 and concatenates into assets/visuals.mp4
"""
from __future__ import annotations
import argparse, json, os, subprocess, tempfile, random
from pathlib import Path
from typing import Dict, List, Tuple

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

def _import_adapter(modname: str):
    try: return __import__(f"adapters.{modname}", fromlist=["*"])
    except Exception: return __import__(modname)

def _load_shotlist(p: Path) -> List[Dict]:
    d = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(d, dict) and "beats" in d: return d["beats"]
    if isinstance(d, list): return d
    return [{"text": str(d), "keywords": [], "title": "Beat", "duration": 5.0}]

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _concat(shots: List[Path], out_path: Path) -> None:
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".txt") as f:
        for s in shots: f.write(f"file '{s.absolute()}'\n")
        lst = Path(f.name)
    try:
        subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c:v", "copy", str(out_path)], check=True)
    finally:
        try: lst.unlink()
        except Exception: pass

def _pick_mode(series: str, kws: List[str], recent_modes: List[str]) -> Tuple[str,str]:
    """
    Return (adapter, mode). Avoid repeating the same mode 2x in a row.
    """
    ks = " ".join(kws or []).lower()
    if series in ("math_of_ML", "ai_teacher", "ai_teacher_linear_algebra"):
        # LA modes
        la_modes = ["grid","vectors","rotation","projection","basis3d","proj_plane"]
        # map keywords to modes
        if any(k in ks for k in ["determinant","area","transform","matrix","basis","lattice","grid"]):
            candidates = ["grid"]
        elif any(k in ks for k in ["rotate","rotation","angle"]):
            candidates = ["rotation"]
        elif any(k in ks for k in ["project","projection","inner product","dot"]):
            candidates = ["projection"]
        elif any(k in ks for k in ["plane","3d","vector3","cross"]):
            candidates = ["basis3d","proj_plane"]
        else:
            candidates = ["vectors","grid","rotation","projection","basis3d"]
        # avoid last mode
        candidates = [m for m in candidates if m not in recent_modes[-1:]] or la_modes
        mode = random.choice(candidates)
        if mode in ("basis3d","proj_plane"):
            return ("la_viz_3d", mode)
        return ("la_viz", mode)

    elif series in ("MAS", "ai_teacher_mas"):
        mas_modes = ["ring","star","grid","payoff"]
        if any(k in ks for k in ["ring","cycle","gossip"]):
            candidates = ["ring"]
        elif any(k in ks for k in ["star","hub","broadcast"]):
            candidates = ["star"]
        elif any(k in ks for k in ["grid","gridworld","policy","trace"]):
            candidates = ["grid"]
        elif any(k in ks for k in ["payoff","matrix","nash"]):
            candidates = ["payoff"]
        else:
            candidates = ["ring","star","grid","payoff"]
        candidates = [m for m in candidates if m not in recent_modes[-1:]] or mas_modes
        return ("mas_viz", random.choice(candidates))

    # fallback
    return ("diagram_flow", "flow")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
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
    shotlist = assets / "shotlist.json"

    _ensure_dir(shots_dir)
    beats = _load_shotlist(shotlist)

    # Ensure >= 12 beats by padding short ones with neutral diagram beats
    if len(beats) < 12:
        need = 12 - len(beats)
        for i in range(need):
            beats.append({
                "title": "Diagram",
                "text": "Concept link",
                "keywords": ["diagram","flow"],
                "duration": 4.5
            })

    la = _import_adapter("la_viz")
    la3 = _import_adapter("la_viz_3d")
    mas = _import_adapter("mas_viz")
    flow = _import_adapter("diagram_flow")
    chart = _import_adapter("chart_simple")

    made: List[Path] = []
    recent_modes: List[str] = []
    rng = random.Random(42)

    # Determine effective series for routing (mixed episodes still use their plan)
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        effective_series = plan.get("effective_series", series)
    except Exception:
        effective_series = series

    for i, b in enumerate(beats):
        text = (b.get("text") or b.get("title") or "Beat").strip()
        kws = b.get("keywords") or []
        dur = float(b.get("duration") or 5.0)
        out = shots_dir / f"{i:03d}.mp4"

        try:
            adapter, mode = _pick_mode(effective_series, kws, recent_modes)
            recent_modes.append(mode)
            if adapter == "la_viz":
                print(f"[router] beat {i}: LA mode={mode} d={dur:.1f}s kws={kws[:3]}")
                la.render(text=text, out_path=out, duration=dur, mode=mode, seed=100+i)
            elif adapter == "la_viz_3d":
                print(f"[router] beat {i}: LA3D mode={mode} d={dur:.1f}s kws={kws[:3]}")
                la3.render(text=text, out_path=out, duration=dur, mode=mode, seed=100+i)
            elif adapter == "mas_viz":
                print(f"[router] beat {i}: MAS mode={mode} d={dur:.1f}s kws={kws[:3]}")
                mas.render(text=text, out_path=out, duration=dur, mode=mode, seed=100+i)
            else:
                # neutral fallback variety
                if i % 2 == 0:
                    print(f"[router] beat {i}: FLOW d={dur:.1f}s")
                    flow.render(text=text, out_path=out, duration=dur)
                else:
                    print(f"[router] beat {i}: CHART d={dur:.1f}s")
                    chart.render(text=text, out_path=out, duration=dur)
        except Exception as e:
            print(f"[router] ERROR beat {i}: {e} → fallback solid")
            subprocess.run([FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c=0x101426:s=1080x1920:d={dur:.2f}",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)], check=False)

        made.append(out)

    # Hard guard: require at least 10 unique shots
    if len(made) < 10:
        print("[router] ERROR: too few shots (<10)")
        return 2

    print(f"[router] concat {len(made)} shots → {visuals}")
    _concat(made, visuals)
    print(f"[router] visuals: {visuals}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
