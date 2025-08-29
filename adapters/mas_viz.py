# -*- coding: utf-8 -*-
"""
mas_viz.py
Multi-Agent Systems visuals with several "modes":
  - ring       : ring topology with pulses
  - star       : star topology with pulses
  - grid       : small 2D grid of agents + path trace
  - payoff     : 2x2 payoff matrix reveal
"""
from __future__ import annotations
import math, random
from pathlib import Path
from typing import Optional, Literal, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
import numpy as np

W, H = 1080, 1920
DPI = 100
FIGSIZE = (W / DPI, H / DPI)

Mode = Literal["ring","star","grid","payoff"]

def _base(fig):
    ax = fig.add_subplot(111)
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-2.2, 2.2)
    ax.set_aspect("equal")
    ax.set_facecolor("#101426")
    ax.axis("off")
    return ax

def _layout_ring(n: int) -> List[Tuple[float,float]]:
    return [(math.cos(2*math.pi*i/n), math.sin(2*math.pi*i/n)) for i in range(n)]

def render(text: str, out_path: Path, duration: float = 5.5, fps: int = 24, mode: Optional[Mode] = "ring", seed: int = 0) -> None:
    out_path = Path(out_path)
    frames = max(int(duration * fps), 12)
    rng = np.random.default_rng(seed)
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = _base(fig)
    title = ax.text(0.5, 0.95, text[:90], ha="center", va="top", color="white", transform=ax.transAxes, fontsize=16)

    writer = FFMpegWriter(fps=fps, metadata={"title": f"MAS:{mode}"}, bitrate=2400)

    with writer.saving(fig, str(out_path), DPI):
        if mode in ("ring","star"):
            n = 6 if mode == "ring" else 7
            pts = _layout_ring(n)
            center = (0.0, 0.0)
            edges = []
            if mode == "ring":
                edges = [(i,(i+1)%n) for i in range(n)]
            else:
                edges = [(i,n-1) for i in range(n-1)]  # star (last node as hub)

            # Draw base
            for t in range(frames):
                ax.cla(); _base(fig)
                title = ax.text(0.5, 0.95, text[:90], ha="center", va="top", color="white", transform=ax.transAxes, fontsize=16)
                # nodes
                for i,(x,y) in enumerate(pts):
                    ax.plot([x],[y], marker="o", markersize=12, color="#e2e8f0")
                    ax.text(x, y-0.12, f"A{i+1}", color="#94a3b8", ha="center", va="top", fontsize=10)
                # edges
                for i,j in edges:
                    x1,y1 = pts[i]; x2,y2 = pts[j]
                    ax.plot([x1,x2],[y1,y2], color="#334155", linewidth=2)
                # pulse along an edge
                eidx = (t // 8) % len(edges)
                i,j = edges[eidx]
                tt = (t % 8)/8.0
                x = pts[i][0]*(1-tt) + pts[j][0]*tt
                y = pts[i][1]*(1-tt) + pts[j][1]*tt
                ax.plot([x],[y], marker="o", markersize=8, color="#67e8f9")
                writer.grab_frame()

        elif mode == "grid":
            # 3x4 agents with a path trace (random walk)
            gx, gy = 3, 4
            xs = np.linspace(-1.0, 1.0, gx)
            ys = np.linspace(-1.8, 1.8, gy)
            agents = [(x,y) for y in ys for x in xs]
            # random walk over agents
            idx = rng.integers(0, len(agents))
            path = [idx]
            for _ in range(frames):
                nbrs = [idx-1, idx+1, idx-gx, idx+gx]
                nbrs = [k for k in nbrs if 0 <= k < len(agents)]
                idx = rng.choice(nbrs)
                path.append(idx)

            for t in range(frames):
                ax.cla(); _base(fig)
                title = ax.text(0.5, 0.95, text[:90], ha="center", va="top", color="white", transform=ax.transAxes, fontsize=16)
                for (x,y) in agents:
                    ax.plot([x],[y], marker="o", markersize=8, color="#e2e8f0")
                # draw last 20 steps
                seg = path[max(0,t-20):t+1]
                for a,b in zip(seg, seg[1:]):
                    x1,y1 = agents[a]; x2,y2 = agents[b]
                    ax.plot([x1,x2],[y1,y2], color="#67e8f9", linewidth=2)
                writer.grab_frame()

        else:  # payoff
            # 2x2 payoff matrix reveal
            for t in range(frames):
                ax.cla(); _base(fig)
                title = ax.text(0.5, 0.95, text[:90], ha="center", va="top", color="white", transform=ax.transAxes, fontsize=16)
                # draw table boundaries
                x0,y0 = -0.8, 0.2
                w,h = 1.6, 1.6
                ax.add_patch(plt.Rectangle((x0,y0-h), w, h, fill=False, edgecolor="#e2e8f0", linewidth=2))
                ax.plot([x0, x0+w],[y0-h/2, y0-h/2], color="#e2e8f0")
                ax.plot([x0+w/2, x0+w/2],[y0, y0-h], color="#e2e8f0")
                # slow reveal of numbers
                alpha = (t+1)/frames
                vals = np.array([[3,1],[0,2]])
                for i in range(2):
                    for j in range(2):
                        xv = x0 + (j+0.5)*(w/2)
                        yv = y0 - (i+0.5)*(h/2)
                        ax.text(xv, yv, f"{vals[i,j]}", ha="center", va="center",
                                color="#67e8f9", fontsize=32, alpha=alpha)
                writer.grab_frame()
    plt.close(fig)
