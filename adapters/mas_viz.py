# -*- coding: utf-8 -*-
"""
Multi-Agent Systems visuals (matplotlib + simple sim).
We draw a small agent graph and animate message "pulses" along edges.
"""
from __future__ import annotations
import math, random
from pathlib import Path
from typing import List, Tuple
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter

W, H = 1080, 1920
DPI = 100
FIGSIZE = (W / DPI, H / DPI)

def _layout(n: int) -> List[Tuple[float,float]]:
    # Circular layout for simplicity
    return [(math.cos(2*math.pi*i/n), math.sin(2*math.pi*i/n)) for i in range(n)]

def render(text: str, out_path: Path, duration: float = 6.0, fps: int = 24) -> None:
    out_path = Path(out_path)
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = fig.add_subplot(111)
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-2.2, 2.2)
    ax.set_aspect("equal")
    ax.set_facecolor("#101426")
    ax.axis("off")

    txt = ax.text(0.5, 0.95, text[:90], ha="center", va="top", color="white",
                  transform=ax.transAxes, fontsize=16)

    # Simple graph
    n = 6
    pts = _layout(n)
    edges = [(i, (i+1) % n) for i in range(n)] + [(0, 3)]  # ring + one chord

    # draw nodes & edges
    for i, (x,y) in enumerate(pts):
        ax.plot([x],[y], marker="o", markersize=12, color="#e2e8f0")
        ax.text(x, y-0.12, f"A{i+1}", color="#94a3b8", ha="center", va="top", fontsize=10)
    for i,j in edges:
        x1,y1 = pts[i]; x2,y2 = pts[j]
        ax.plot([x1,x2], [y1,y2], color="#334155", linewidth=2)

    # Pulse animation along edges
    frames = max(int(duration * fps), 12)
    writer = FFMpegWriter(fps=fps, metadata={"title": "MAS Viz"}, bitrate=2400)

    # pre-pick pulse path (edge list)
    path = edges * 4

    pulse, = ax.plot([pts[0][0]], [pts[0][1]], marker="o", markersize=8, color="#67e8f9")

    def interp(a, b, t):
        return (a[0]*(1-t)+b[0]*t, a[1]*(1-t)+b[1]*t)

    with writer.saving(fig, str(out_path), DPI):
        for k in range(frames):
            eidx = (k // 8) % len(path)
            i, j = path[eidx]
            t = (k % 8)/8.0
            x, y = interp(pts[i], pts[j], t)
            pulse.set_data([x], [y])
            writer.grab_frame()
    plt.close(fig)
