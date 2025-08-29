# -*- coding: utf-8 -*-
"""
la_viz.py
2D Linear Algebra visuals with several "modes" so beats don't look identical.
Modes:
  - vectors      : two moving vectors with gentle pan
  - grid         : 2x2 matrix deforming a lattice
  - rotation     : rotating a vector around origin
  - projection   : projecting a vector onto a line
We pick the mode in route_shots.py; this module just renders it.

Output: 1080x1920 mp4 (FFMpegWriter)
"""
from __future__ import annotations
import math
from pathlib import Path
from typing import Optional, Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
import numpy as np

W, H = 1080, 1920
DPI = 100
FIGSIZE = (W / DPI, H / DPI)

Mode = Literal["vectors", "grid", "rotation", "projection"]

def _axes(ax):
    ax.set_xlim(-3, 3)
    ax.set_ylim(-5, 5)
    ax.set_aspect("equal")
    ax.set_facecolor("#101426")
    for s in ax.spines.values():
        s.set_color("white")
    ax.tick_params(colors="white", labelsize=10)
    ax.grid(color="#1f2a44", linestyle="--", linewidth=0.5, alpha=0.6)

def render(text: str, out_path: Path, duration: float = 5.5, fps: int = 24, mode: Optional[Mode] = "vectors", seed: int = 0) -> None:
    out_path = Path(out_path)
    frames = max(int(duration * fps), 12)
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = fig.add_subplot(111)
    _axes(ax)
    rng = np.random.default_rng(seed)
    txt = ax.text(0.5, 0.96, text[:90], ha="center", va="top", color="white",
                  transform=ax.transAxes, fontsize=16, wrap=True)

    writer = FFMpegWriter(fps=fps, metadata={"title": f"LA:{mode}"}, bitrate=2400)

    with writer.saving(fig, str(out_path), DPI):
        if mode == "grid":
            # deform a lattice by a 2x2 matrix A(t)
            # base grid
            x = np.linspace(-3, 3, 13)
            y = np.linspace(-5, 5, 21)
            X, Y = np.meshgrid(x, y)
            for t in range(frames):
                ax.cla(); _axes(ax)
                ang = 2*math.pi*(t/frames)*0.15
                A = np.array([[1.0+0.2*math.cos(ang), 0.3*math.sin(ang)],
                              [0.1*math.sin(ang), 1.0-0.2*math.cos(ang)]])
                pts = np.stack([X.flatten(), Y.flatten()], axis=0)
                tr = A @ pts
                # draw transformed verticals/horizontals
                for i in range(X.shape[0]):  # rows (horiz lines)
                    p = (A @ np.stack([X[i, :], Y[i, :]]))  # 2xN
                    ax.plot(p[0], p[1], color="#334155", linewidth=0.8)
                for j in range(X.shape[1]):  # cols (vert lines)
                    p = (A @ np.stack([X[:, j], Y[:, j]]))
                    ax.plot(p[0], p[1], color="#334155", linewidth=0.8)
                txt.set_text(text[:90])
                writer.grab_frame()

        elif mode == "rotation":
            v = np.array([2.2, 1.4])
            for t in range(frames):
                ax.cla(); _axes(ax)
                ang = 2*math.pi*(t/frames)*0.35
                R = np.array([[math.cos(ang), -math.sin(ang)],
                              [math.sin(ang),  math.cos(ang)]])
                w = R @ v
                ax.arrow(0,0, w[0], w[1], width=0.06, color="#a78bfa", length_includes_head=True)
                ax.plot([0,w[0]], [0,w[1]], color="#a78bfa", linewidth=3)
                txt.set_text(text[:90])
                writer.grab_frame()

        elif mode == "projection":
            v = np.array([2.0, 1.5])
            u = np.array([1.0, 0.6]); u = u / np.linalg.norm(u)
            for t in range(frames):
                ax.cla(); _axes(ax)
                # gently change v angle
                ang = 2*math.pi*(t/frames)*0.25
                R = np.array([[math.cos(ang), -math.sin(ang)],
                              [math.sin(ang),  math.cos(ang)]])
                vv = R @ v
                # projection of vv onto u
                proj = (vv @ u) * u
                ax.arrow(0,0, vv[0], vv[1], width=0.05, color="#67e8f9", length_includes_head=True)
                ax.arrow(0,0, proj[0], proj[1], width=0.05, color="#22d3ee", length_includes_head=True)
                # draw u
                ax.plot([0,u[0]*3], [0,u[1]*3], color="#334155", linestyle="--")
                txt.set_text(text[:90])
                writer.grab_frame()

        else:  # vectors
            v1 = np.array([2.0, 1.0])
            v2 = np.array([1.0, 2.5])
            for t in range(frames):
                ax.cla(); _axes(ax)
                ang = 2*math.pi*(t/frames)*0.15
                s = 1.0 + 0.08*math.sin(2*math.pi*(t/frames))
                R1 = np.array([[math.cos(ang), -math.sin(ang)],
                               [math.sin(ang),  math.cos(ang)]])
                R2 = np.array([[math.cos(-ang*0.7), -math.sin(-ang*0.7)],
                               [math.sin(-ang*0.7),  math.cos(-ang*0.7)]])
                w1 = s * (R1 @ v1); w2 = s * (R2 @ v2)
                ax.arrow(0,0, w1[0], w1[1], width=0.05, color="#67e8f9", length_includes_head=True)
                ax.arrow(0,0, w2[0], w2[1], width=0.05, color="#a78bfa", length_includes_head=True)
                txt.set_text(text[:90])
                writer.grab_frame()

    plt.close(fig)
