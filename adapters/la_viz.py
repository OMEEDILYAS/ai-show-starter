# -*- coding: utf-8 -*-
"""
Linear Algebra visuals (matplotlib) — no external assets.
Creates simple, clean 1080x1920 animations:
 - moving vectors on a 2D grid
 - gentle camera pan so it doesn't look static

We use matplotlib.animation with ffmpeg writer (already in your workflow).
"""
from __future__ import annotations
import math
from pathlib import Path
from typing import Optional
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter

W, H = 1080, 1920  # portrait
DPI = 100
FIGSIZE = (W / DPI, H / DPI)

def _axes(ax):
    ax.set_xlim(-3, 3)
    ax.set_ylim(-5, 5)
    ax.set_aspect("equal")
    ax.set_facecolor("#101426")
    ax.spines["bottom"].set_color("white")
    ax.spines["left"].set_color("white")
    ax.spines["top"].set_color("#101426")
    ax.spines["right"].set_color("#101426")
    ax.tick_params(colors="white", labelsize=10)
    ax.grid(color="#1f2a44", linestyle="--", linewidth=0.5, alpha=0.6)

def render(text: str, out_path: Path, duration: float = 6.0, fps: int = 24) -> None:
    """
    Create a simple vector field animation with 1–2 vectors that rotate/scale slightly.
    """
    out_path = Path(out_path)
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = fig.add_subplot(111)
    _axes(ax)

    # Base vectors (we tweak them over time)
    v1 = [2.0, 1.0]
    v2 = [1.0, 2.5]

    frames = max(int(duration * fps), 12)
    writer = FFMpegWriter(fps=fps, metadata={"title": "LA Viz"}, bitrate=2400)
    txt = ax.text(0.5, 0.96, text[:90], ha="center", va="top", color="white",
                  transform=ax.transAxes, fontsize=16, wrap=True)

    arrow1 = ax.arrow(0, 0, v1[0], v1[1], width=0.04, color="#67e8f9", length_includes_head=True)
    arrow2 = ax.arrow(0, 0, v2[0], v2[1], width=0.04, color="#a78bfa", length_includes_head=True)

    with writer.saving(fig, str(out_path), DPI):
        for t in range(frames):
            # gentle rotation/scaling
            ang = 2 * math.pi * (t / frames) * 0.15
            s = 1.0 + 0.08 * math.sin(2 * math.pi * (t / frames))

            def rot(x, y, a):
                return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)

            x1, y1 = rot(2.0, 1.0, ang)
            x2, y2 = rot(1.0, 2.5, -ang * 0.7)

            # Update arrows (recreate for simplicity)
            for a in [arrow1, arrow2]:
                a.remove()
            arrow1 = ax.arrow(0, 0, s * x1, s * y1, width=0.04, color="#67e8f9", length_includes_head=True)
            arrow2 = ax.arrow(0, 0, s * x2, s * y2, width=0.04, color="#a78bfa", length_includes_head=True)

            # Slow vertical pan to avoid static feel
            ylim = (-5 + 0.2 * math.sin(2 * math.pi * (t / frames)), 5 + 0.2 * math.sin(2 * math.pi * (t / frames)))
            ax.set_ylim(*ylim)

            writer.grab_frame()
    plt.close(fig)
