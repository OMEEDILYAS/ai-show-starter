# -*- coding: utf-8 -*-
"""
Simple charts (bar/line) with animated reveal using matplotlib.
"""
from __future__ import annotations
import random
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter

W, H = 1080, 1920
DPI = 100
FIGSIZE = (W / DPI, H / DPI)

def render(text: str, out_path: Path, duration: float = 6.0, fps: int = 24) -> None:
    out_path = Path(out_path)

    # fake data tied to text length (deterministic-ish)
    n = 5
    seed = len(text)
    random.seed(seed)
    vals = [random.randint(3, 10) for _ in range(n)]
    labels = [f"c{i+1}" for i in range(n)]

    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = fig.add_subplot(111)
    ax.set_facecolor("#101426")
    ax.tick_params(colors="white")
    for s in ax.spines.values():
        s.set_color("white")
    ax.set_ylim(0, max(vals) + 2)
    bars = ax.bar(labels, [0]*n, color="#67e8f9")
    ax.set_title(text[:80], color="white", fontsize=16)

    frames = max(int(duration*fps), 12)
    writer = FFMpegWriter(fps=fps, metadata={"title":"Chart"}, bitrate=2000)
    with writer.saving(fig, str(out_path), DPI):
        for k in range(frames):
            t = (k+1)/frames
            for bi, b in enumerate(bars):
                b.set_height(vals[bi]*t)
            writer.grab_frame()
    plt.close(fig)
