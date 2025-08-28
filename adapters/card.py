"""
Card adapter (robust + deterministic):
- Structured visual over bg.mp4 (never blank).
- Uses a chosen stock clip when provided by the router (override_clip).
- Otherwise searches stock_dir recursively (case-insensitive .mp4/.mov).
- Prints clear logs so you can see what clip it used.
"""

from __future__ import annotations
import glob
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

FFMPEG = "ffmpeg"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def _gather_candidates(stock_dir: Path) -> list[Path]:
    if not stock_dir or not stock_dir.exists():
        return []
    patterns = [
        str(stock_dir / "**/*.mp4"),
        str(stock_dir / "**/*.MP4"),
        str(stock_dir / "**/*.mov"),
        str(stock_dir / "**/*.MOV"),
    ]
    files: list[Path] = []
    for pat in patterns:
        files.extend(Path(p) for p in glob.glob(pat, recursive=True))
    uniq = sorted({p.resolve() for p in files if p.is_file()})
    return uniq

def _pick_stock_clip(stock_dir: Path, keywords: List[str]) -> Optional[Path]:
    candidates = _gather_candidates(stock_dir)
    if not candidates:
        print(f"[card] no stock candidates under: {stock_dir}")
        return None
    kw_norm = [k.lower() for k in (keywords or []) if isinstance(k, str)]
    scored = []
    for p in candidates:
        name = p.name.lower()
        score = sum(1 for k in kw_norm if k and k in name)
        scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].name))
    best_score, best_path = scored[0]
    print(f"[card] auto-pick stock: candidates={len(candidates)} best_score={best_score} picked={best_path}")
    return best_path

def _safe_txt(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
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

def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)

def render(
    bg_path: Path,
    out_path: Path,
    title: str = "",
    text: str = "",
    keywords: Optional[List[str]] = None,
    stock_dir: Optional[Path] = None,
    duration: Optional[float] = None,
    override_clip: Optional[Path] = None,   # NEW: router can force a specific clip
) -> None:
    """
    Create a 1080x1920 card:
      - bg.mp4 as background
      - centered card with border/shadow
      - 16:9 video panel (override_clip > stock_dir pick > bg)
      - title + up to 4 bullet keywords
    """
    keywords = keywords or []
    if duration is None:
        duration = 5.9

    # Decide panel content deterministically if router gave us one.
    clip_path = None
    if override_clip and Path(override_clip).exists():
        clip_path = Path(override_clip)
        print(f"[card] override_clip supplied by router: {clip_path}")
    elif stock_dir is not None:
        clip_path = _pick_stock_clip(stock_dir, keywords)

    if clip_path is None:
        clip_path = bg_path
        print("[card] WARNING: no stock clip selected; using bg as panel content.")

    # Layout constants
    W, H = 1080, 1920
    card_margin_x = 72
    card_margin_y = 180
    card_w = W - card_margin_x * 2
    card_h = H - card_margin_y * 2
    card_x = card_margin_x
    card_y = card_margin_y

    panel_w = 960
    panel_h = int(panel_w * 9 / 16)
    panel_x = (W - panel_w) // 2
    panel_y = card_y + 160

    title_y = card_y + 40
    bullets_y = panel_y + panel_h + 120
    title_size = 56
    bullet_size = 40

    title_text = _safe_txt(title or text or "")
    bullets_text = _safe_txt(_wrap_bullets(keywords))
    title_file = _write_text_tmp(title_text)
    bullets_file = _write_text_tmp(bullets_text)

    scale_bg = f"scale={W}:{H},format=yuv420p"
    shadow = f"drawbox=x={card_x+12}:y={card_y+16}:w={card_w}:h={card_h}:t=20:color=black@0.35"
    fill   = f"drawbox=x={card_x}:y={card_y}:w={card_w}:h={card_h}:t=fill:color=white@0.06"
    border = f"drawbox=x={card_x}:y={card_y}:w={card_w}:h={card_h}:t=6:color=white@0.7"

    clip_fit = (
        f"scale=w={panel_w}:h={panel_h}:force_original_aspect_ratio=cover,"
        f"crop={panel_w}:{panel_h},setsar=1"
    )
    overlay_clip = f"overlay=x={panel_x}:y={panel_y}:format=auto"

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
    cmd = [
        FFMPEG, "-y",
        "-i", str(bg_path),
        "-i", str(clip_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-level", "4.0", "-preset", "veryfast",
        "-movflags", "+faststart",
        str(out_path),
    ]

    try:
        _run(cmd)
    finally:
        try: title_file.unlink(missing_ok=True)
        except Exception: pass
        try: bullets_file.unlink(missing_ok=True)
        except Exception: pass
