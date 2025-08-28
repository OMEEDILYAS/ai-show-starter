#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
planner/plan_next.py
PURPOSE:
  - Validates the requested --series (math_of_ML, MAS, mixed).
  - Loads config/series.yml to resolve the real curriculum (book_slug).
  - Reads data/cursor.json to find the next chunk.
  - Locates the pre-split text chunk from data/curriculum/<book>/chXX/.
  - Creates a new episode directory out/<series>/ep_<stamp>/ with a plan.json
    that downstream steps (agent_director, make_shotlist, route_shots, etc.) will use.

REQUIREMENTS:
  - pyyaml installed in the workflow (pip install pyyaml).
  - Your pre-split text files and chapter_index.json exist under:
      data/curriculum/<book_slug>/chXX/*.txt
      data/curriculum/<book_slug>/chXX/chapter_index.json

NOTES:
  - We do NOT set 'video_path' in plan.json here; build_video.py will fill it later.
  - If series == "mixed", we pick a real series uniformly at random from config["series"]["mixed"]["options"].
"""

import argparse  # parses CLI args
import json      # read/write plan.json / cursor.json
import random    # for uniform random pick in 'mixed'
import time      # to stamp episode folders
from pathlib import Path  # file paths
import yaml      # read config/series.yml

# ---------- CONSTANT PATHS ----------
ROOT = Path(__file__).resolve().parents[1]  # comment: repo root (one level up from planner/)
CONFIG_PATH = ROOT / "config" / "series.yml"  # comment: our new series config
CURSOR_PATH = ROOT / "data" / "cursor.json"   # comment: global cursor state
CURR_DIR = ROOT / "data" / "curriculum"       # comment: where pre-split chapter text lives
OUT_DIR = ROOT / "out"                         # comment: where episodes are written


def _load_yaml_config() -> dict:
    """Load config/series.yml and return its dict."""
    # comment: Ensure the config file exists; if not, fail with a clear message
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config: {CONFIG_PATH}. Create it (see config/series.yml template).")
    # comment: Read YAML as a Python dict
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _load_cursor() -> dict:
    """Load or initialize data/cursor.json."""
    # comment: If cursor.json does not exist, initialize with defaults we agreed on
    if not CURSOR_PATH.exists():
        CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)  # comment: ensure data/ exists
        default = {
            "math_of_ML": {"chapter": 2, "section": "01-chapter", "part": 1},
            "MAS":        {"chapter": 1, "section": "01-chapter", "part": 1},
            "mixed":      {"series": "math_of_ML", "chapter": 2, "section": "01-chapter", "part": 1}
        }
        CURSOR_PATH.write_text(json.dumps(default, indent=2), encoding="utf-8")  # comment: write defaults
    # comment: Return parsed JSON as dict
    return json.loads(CURSOR_PATH.read_text(encoding="utf-8"))


def _chapter_dir(book_slug: str, chapter: int) -> Path:
    """Return the path to data/curriculum/<book_slug>/chXX/."""
    # comment: Build the folder name chXX with zero-padded chapter number
    return CURR_DIR / book_slug / f"ch{chapter:02d}"


def _load_chapter_index(book_slug: str, chapter: int) -> dict:
    """Load the per-chapter index listing chunk files in order."""
    # comment: chapter_index.json tells us the exact files in order for this chapter
    p = _chapter_dir(book_slug, chapter) / "chapter_index.json"
    if not p.exists():
        raise FileNotFoundError(f"Missing chapter index: {p} (did you run the splitter and commit outputs?)")
    return json.loads(p.read_text(encoding="utf-8"))


def _resolve_series(cfg: dict, requested_series: str) -> tuple[str, str]:
    """
    Return (effective_series, book_slug).
    - If requested_series == "mixed": pick a real series uniformly at random.
    - Otherwise: return (requested_series, cfg["series"][requested_series]["book_slug"])
    """
    # comment: Pull the top-level 'series' key from YAML config
    series_map = (cfg or {}).get("series") or {}
    # comment: Fail fast if the 'series' block isn't present
    if not series_map:
        raise KeyError("config/series.yml is missing the top-level 'series:' mapping.")

    # comment: If 'mixed' was requested, pick from options
    if requested_series == "mixed":
        mixed_cfg = series_map.get("mixed") or {}
        options = mixed_cfg.get("options") or []
        if not options:
            # comment: If no options listed, default to math_of_ML only
            options = ["math_of_ML"]
        chosen = random.choice(options)  # comment: uniform random pick
        # comment: Resolve chosen series to its book_slug
        chosen_cfg = series_map.get(chosen)
        if not chosen_cfg:
            raise KeyError(f"Series '{chosen}' from mixed.options not found in config.")
        book_slug = chosen_cfg.get("book_slug")
        if not book_slug:
            raise KeyError(f"Series '{chosen}' missing 'book_slug' in config/series.yml.")
        return chosen, book_slug

    # comment: Non-mixed: validate the requested series exists
    s_cfg = series_map.get(requested_series)
    if not s_cfg:
        # comment: Show the user which valid keys are available to fix typos quickly
        valid = ", ".join(sorted(series_map.keys()))
        raise KeyError(f"Unknown series '{requested_series}'. Valid series: {valid}")

    # comment: Pull the book_slug that points to the curriculum folder
    book_slug = s_cfg.get("book_slug")
    if not book_slug:
        raise KeyError(f"Series '{requested_series}' missing 'book_slug' in config/series.yml.")
    return requested_series, book_slug


def _pick_chunk(book_slug: str, chapter: int, section_stem: str) -> tuple[Path, str]:
    """
    Given book/chapter/section stem, return (file_path, normalized_stem).
    We treat each listed filename in chapter_index.json as one atomic 'part'.
    """
    # comment: Load chapter index and read its ordered file list
    ch_idx = _load_chapter_index(book_slug, chapter)
    files = ch_idx.get("files") or []
    if not files:
        raise RuntimeError(f"No files listed in {book_slug} ch{chapter:02d} index.")
    # comment: Try to find the current section stem in files; fallback to first
    try:
        # comment: exact match with extension
        i = files.index(f"{section_stem}.txt")
    except ValueError:
        # comment: if plan stored '01-chapter-part1' but files have '01-chapter-part1.txt'
        matches = [k for k in files if k.startswith(section_stem)]
        i = files.index(matches[0]) if matches else 0
    # comment: Build absolute path to that file
    p = _chapter_dir(book_slug, chapter) / files[i]
    # comment: normalized stem (without .txt)
    stem = Path(files[i]).stem
    return p, stem


def _make_episode_dirs(series: str) -> Path:
    """Create out/<series>/ep_<timestamp>/assets and return the ep dir."""
    # comment: The timestamp gives us a unique episode folder
    stamp = int(time.time())
    ep_dir = OUT_DIR / series / f"ep_{stamp}"
    assets = ep_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    return ep_dir


def main():
    # comment: Parse the --series argument (required)
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True, help="Series slug: math_of_ML | MAS | mixed")
    args = ap.parse_args()

    # comment: Load config and cursor from disk
    cfg = _load_yaml_config()
    cur = _load_cursor()

    # comment: Resolve requested series → effective series + book_slug
    effective_series, book_slug = _resolve_series(cfg, args.series)

    # comment: Pull cursor state for the effective series; 'mixed' keeps its own entry but we use the chosen series for curriculum
    cur_entry = cur.get(effective_series) or {}
    chapter = int(cur_entry.get("chapter") or 1)
    section = str(cur_entry.get("section") or "01-chapter")

    # comment: Find the text chunk file for this (book, chapter, section)
    chunk_path, normalized_section = _pick_chunk(book_slug, chapter, section)

    # comment: Create a fresh episode folder under the REQUESTED series (so mixed keeps its own timeline folders)
    ep_dir = _make_episode_dirs(args.series)
    assets = ep_dir / "assets"

    # comment: Write the source text into assets so later stages can read it directly
    source_txt = assets / "source.txt"
    source_txt.write_text(chunk_path.read_text(encoding="utf-8"), encoding="utf-8")

    # comment: Prepare a minimal plan.json that downstream expects
    # - We do NOT set "video_path" here; build_video.py will populate the final path.
    plan = {
        "series": args.series,               # the requested series (may be 'mixed')
        "effective_series": effective_series,# the real series used for curriculum
        "book_slug": book_slug,              # curriculum folder used
        "chapter": chapter,                  # chapter number (int)
        "section": normalized_section,       # file stem (e.g., 01-chapter or 02-vectors-part1)
        "assets_dir": str(assets),           # where assets will be written
        "created_at": int(time.time())       # epoch seconds (for reference)
    }
    (ep_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    # comment: Also write simple labels for title/overlay placeholders (director will refine)
    (assets / "title.txt").write_text(f"{effective_series} — Chapter {chapter}", encoding="utf-8")
    (assets / "overlay.txt").write_text(f"Section: {normalized_section}", encoding="utf-8")

    # comment: Log what we planned for quick debugging in CI
    print(f"[plan_next] series={args.series} effective={effective_series} book={book_slug}")
    print(f"[plan_next] chapter={chapter} section={normalized_section}")
    print(f"[plan_next] chunk={chunk_path}")
    print(f"[plan_next] ep_dir={ep_dir}")

if __name__ == "__main__":
    main()
