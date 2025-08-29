# -*- coding: utf-8 -*-
"""
la_viz_3d.py
Simple 3D linear algebra visuals using matplotlib's mplot3d.
Scenes:
  - rotating 3D basis vectors
  - projection of a vector onto a plane
Generates 1080x1920 mp4 via FFMpegWriter (already present in workflow).
"""
from __future__ import annotations
import math
from pathlib import Path
from typing import Literal, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (forces 3D support)
from matplotlib.animation import FFMpegWriter

W, H = 1080, 1920
DPI = 100
FIGSIZE = (W / DPI, H / DPI)

Mode = Literal["basis3d", "proj_plane"]

def _axes3d(ax):
    ax.set_xlim([-2, 2]); ax.set_ylim([-2, 2]); ax.set_zlim([-2, 2])
    ax.set_box_aspect([1, 1, 1])
    ax.set_facecolor("#101426")
    ax.grid(False)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])

def render(text: str, out_path: Path, duration: float = 5.5, fps: int = 24, mode: Optional[Mode] = None, seed: int = 0) -> None:
    out_path = Path(out_path)
    if mode not in ("basis3d", "proj_plane"):
        mode = "basis3d"

    frames = max(int(duration * fps), 12)
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = fig.add_subplot(111, projection="3d")
    _axes3d(ax)
    title = ax.text2D(0.5, 0.96, text[:80], transform=ax.transAxes, ha="center", va="top", color="white", fontsize=14)

    writer = FFMpegWriter(fps=fps, metadata={"title": f"LA3D:{mode}"}, bitrate=2500)

    with writer.saving(fig, str(out_path), DPI):
        if mode == "basis3d":
            # draw basis vectors e1,e2,e3 and rotate camera
            for t in range(frames):
                ax.cla(); _axes3d(ax)
                ax.quiver(0,0,0, 1,0,0, color="#67e8f9", linewidth=3)
                ax.quiver(0,0,0, 0,1,0, color="#a78bfa", linewidth=3)
                ax.quiver(0,0,0, 0,0,1, color="#f472b6", linewidth=3)
                # camera spin
                az = (t / frames) * 360
                el = 20 + 10 * math.sin(2*math.pi*(t/frames))
                ax.view_init(elev=el, azim=az)
                title.set_text(text[:80])
                writer.grab_frame()
        else:
            # projection of vector onto plane z=0.5
            import numpy as np
            X, Y = np.meshgrid(np.linspace(-1.2,1.2,10), np.linspace(-1.2,1.2,10))
            Z = 0*X + 0.5
            v = np.array([1.0, 1.0, 1.5])
            plane_n = np.array([0,0,1.0])
            for t in range(frames):
                ax.cla(); _axes3d(ax)
                ax.plot_surface(X, Y, Z, alpha=0.2, color="#64748b")
                # rotate v slowly
                ang = 2*math.pi*(t/frames)*0.4
                R = np.array([[math.cos(ang), -math.sin(ang), 0],
                              [math.sin(ang),  math.cos(ang), 0],
                              [0, 0, 1]])
                vv = R @ v
                # projection onto plane
                vv_proj = vv - (vv @ plane_n) * plane_n
                ax.quiver(0,0,0, *vv, color="#67e8f9", linewidth=3)
                ax.quiver(0,0,0, *vv_proj, color="#a78bfa", linewidth=3)
                az = 45 + (t / frames) * 90
                el = 25
                ax.view_init(elev=el, azim=az)
                title.set_text(text[:80])
                writer.grab_frame()
    plt.close(fig)
