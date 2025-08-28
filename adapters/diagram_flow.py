# -*- coding: utf-8 -*-
"""
Graphviz flow diagram → PNG → subtle pan in matplotlib movie (keeps everything in-Python).
Requires system 'graphviz' and Python package 'graphviz' (vendor wheel or pip).
"""
from __future__ import annotations
import tempfile
from pathlib import Path
import graphviz
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter

W, H = 1080, 1920
DPI = 100
FIGSIZE = (W / DPI, H / DPI)

def render(text: str, out_path: Path, duration: float = 6.0, fps: int = 24) -> None:
    out_path = Path(out_path)

    # 1) Build a tiny flow based on the text (break into 3–4 bullets)
    bullets = [s.strip() for s in text.replace("—","-").split(".") if s.strip()][:4]
    if not bullets:
        bullets = ["Idea", "Step", "Example", "Conclusion"]

    dot = graphviz.Digraph(format="png")
    dot.attr(rankdir="TB", bgcolor="transparent", color="white", fontcolor="white")
    prev = "Start"
    dot.node(prev, prev, shape="circle", color="white", fontcolor="white")
    for i, b in enumerate(bullets, 1):
        nid = f"N{i}"
        dot.node(nid, b[:40], shape="box", color="white", fontcolor="white")
        dot.edge(prev, nid, color="white")
        prev = nid

    with tempfile.TemporaryDirectory() as td:
        png_path = Path(dot.render(directory=td, cleanup=True))
        # 2) Simple pan animation in matplotlib
        fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#101426"); ax.axis("off")
        img = plt.imread(str(png_path))
        im = ax.imshow(img, extent=[0,1,0,1])

        frames = max(int(duration*fps), 12)
        writer = FFMpegWriter(fps=fps, metadata={"title":"Flow"}, bitrate=2000)
        with writer.saving(fig, str(out_path), DPI):
            for k in range(frames):
                # slow zoom-in
                z = 1.05 + 0.05 * (k/frames)
                im.set_extent([0.5-0.5/z, 0.5+0.5/z, 0.5-0.5/z, 0.5+0.5/z])
                writer.grab_frame()
        plt.close(fig)
