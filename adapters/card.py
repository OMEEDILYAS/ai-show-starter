"""
Card adapter:
- Always produces a structured visual over bg.mp4 (so you never get a flat color wash).
- If a stock/library clip exists, it is placed inside the card's video panel.
- Title + bullets are rendered with safe default font.
"""

from __future__ import annotations
import glob
import os
import random
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

FFMPEG = "ffmpeg"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def _pick_stock_clip(stock_dir: Path, keywords: List[str]) -> Optional[Path]:
    """
    Choose a stock clip. Try to match any keyword in filename; else first found; else None.
    """
    if not stock_dir.exists():
        return None
    candidates = sorted(Path(p) for p in glob.glob(str(stock_dir / "*.mp4")))
    if not candidates:
        return None

    # simple keyword match on filename
    kw_norm = [k.lower() for k in keywords if isinstance(k, str)]
    scored = []
    for p in candidates:
        name = p.name.lower()
        score = sum(1 for k in kw_norm if k and k in name)
        scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].name))

    best_score, best_path = scored[0]
    if best_score > 0:
        return best_path
    # else: just pick the first (deterministic)
    return candidates[0]

def _safe_txt(s: str) -> str:
    # A minimal sanitization for ffmpeg textfiles
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Avoid weird control chars
    s = re.sub(r"[^\S\n]+", " ", s)
    return s.strip()

def _write_text_tmp(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".txt")
    with tmp as f:
        f.write(content)
    return Path(tmp.name)

def _wrap_bullets(keywords: List[str], max_bullets: int = 4) -> str:
    if not keywords:
        return ""
    items = [f"• {k}" for k in keywords[:max_bullets]]
    return "\n".join(items)

def _run(cmd: List[str]) -> None:
    subprocess.run(cmd, check=True)

def render(
    bg_path: Path,
    out_path: Path,
    title: str = "",
    text: str = "",
    keywords: Optional[List[str]] = None,
    stock_dir: Optional[Path] = None,
    duration: Optional[float] = None
) -> None:
    """
    Create a 1080x1920 card composition:
      - bg.mp4 scaled full frame
      - centered card with border and shadow
      - 16:9 video panel inside the card (stock clip if available, else reuse bg)
      - title + 2–4 bullet keywords
    """
    keywords = keywords or []
    if duration is None:
        duration = 5.9  # default shot length

    stock_clip = None
    if stock_dir is not None:
        stock_clip = _pick_stock_clip(stock_dir, keywords or [])

    # Inputs
    clip_path = stock_clip if stock_clip else bg_path

    # Layout constants (1080x1920 portrait)
    W, H = 1080, 1920

    # Card box
    card_margin_x = 72
    card_margin_y = 180
    card_w = W - card_margin_x * 2         # 936
    card_h = H - card_margin_y * 2         # 1560
    card_x = card_margin_x                 # 72
    card_y = card_margin_y                 # 180

    # Video panel (16:9) centered horizontally near top of card
    panel_w = 960
    panel_h = int(panel_w * 9 / 16)        # 540
    panel_x = (W - panel_w) // 2           # 60
    panel_y = card_y + 160                 # 340

    # Text areas
    title_y = card_y + 40                  # 220
    bullets_y = panel_y + panel_h + 120    # 1000-ish
    title_size = 56
    bullet_size = 40

    # Prepare drawtext files
    title_text = _safe_txt(title or text or "")
    bullets_text = _safe_txt(_wrap_bullets(keywords))

    title_file = _write_text_tmp(title_text)
    bullets_file = _write_text_tmp(bullets_text)

    # Build filter graph
    # 0: bg, 1: clip
    # Steps:
    #   [0:v] scale full -> [bg]
    #   Draw shadow + border card on [bg]
    #   [1:v] scale/crop/pad to panel_w x panel_h -> [clipf]
    #   overlay [clipf] onto card
    #   drawtext title + bullets
    scale_bg = f"scale={W}:{H},format=yuv420p"

    # Card shadow + border using layered drawbox
    # Shadow
    shadow = f"drawbox=x={card_x+12}:y={card_y+16}:w={card_w}:h={card_h}:t=20:color=black@0.35"
    # Card fill
    fill =   f"drawbox=x={card_x}:y={card_y}:w={card_w}:h={card_h}:t=fill:color=white@0.06"
    # Border
    border = f"drawbox=x={card_x}:y={card_y}:w={card_w}:h={card_h}:t=6:color=white@0.7"

    # Clip fitting into panel (cover semantics)
    # scale to cover, then crop to panel
    clip_fit = (
        f"scale=w={panel_w}:h={panel_h}:force_original_aspect_ratio=cover,"
        f"crop={panel_w}:{panel_h},setsar=1"
    )

    # Overlay clip into bg-at-card
    overlay_clip = f"overlay=x={panel_x}:y={panel_y}:format=auto"

    # Text overlays
    title_draw = (
        f"drawtext=fontfile='{FONT}':textfile='{title_file}':"
        f"fontcolor=white:fontsize={title_size}:x=(w-text_w)/2:y={title_y}:"
        f"shadowcolor=black@0.5:shadowx=2:shadowy=2:line_spacing=6"
    )
    bullets_draw = (
        f"drawtext=fontfile='{FONT}':textfile='{bullets_file}':"
        f"fontcolor=white:fontsize={bullet_size}:x=(w-text_w)/2:y={bullets_y}:"
        f"shadowcolor=black@0.5:shadowx=2:shadowy=2:line_spacing=10"
    )

    filter_complex = (
        f"[0:v]{scale_bg},{shadow},{fill},{border}[bg];"
        f"[1:v]{clip_fit}[clipf];"
        f"[bg][clipf]{overlay_clip}[v1];"
        f"[v1]{title_draw}[v2];"
        f"[v2]{bullets_draw}[vout]"
    )

    # Build ffmpeg command
    cmd = [
        FFMPEG, "-y",
        "-i", str(bg_path),
        "-i", str(clip_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-t", f"{duration:.2f}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-level", "4.0",
        "-preset", "veryfast",
        "-movflags", "+faststart",
        str(out_path),
    ]

    try:
        _run(cmd)
    finally:
        # cleanup temp text files
        try:
            title_file.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            bullets_file.unlink(missing_ok=True)
        except Exception:
            pass
