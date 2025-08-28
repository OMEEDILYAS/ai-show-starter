# -*- coding: utf-8 -*-
"""
Helper to pick the next curriculum chunk based on the cursor and index.json.

We never read PDFs in CI. We only read pre-split .txt files:
  data/curriculum/<book_slug>/chXX/chapter_index.json (files order)
  data/curriculum/<book_slug>/chXX/*.txt
"""
import json, random
from pathlib import Path
from typing import Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
CURR = ROOT / "data" / "curriculum"

def _chapter_dir(book_slug: str, chapter: int) -> Path:
    return CURR / book_slug / f"ch{chapter:02d}"

def _load_chapter_index(book_slug: str, chapter: int) -> Dict:
    p = _chapter_dir(book_slug, chapter) / "chapter_index.json"
    if not p.exists():
        raise FileNotFoundError(f"Missing chapter index: {p}")
    return json.loads(p.read_text(encoding="utf-8"))

def pick_next_chunk(book_slug: str, chapter: int, section: str, part: int) -> Tuple[Path, str, int]:
    """
    Return (file_path, section_stem, next_part).
    - section is the filename stem like "01-chapter" or "02-vectors-part1", etc.
    - part is 1-based sub-part index when a section was split into multiple chunks.

    We treat each file in chapter_index.json as an atomic "section part".
    So advancing is simply moving to the next file; when the list ends, caller advances chapter.
    """
    ch_idx = _load_chapter_index(book_slug, chapter)
    files = ch_idx.get("files") or []
    if not files:
        raise RuntimeError(f"No files listed in {book_slug} ch{chapter:02d}")

    # Find current file index
    # We accept both "01-chapter" and "01-chapter-partX" style sections, so search by prefix
    pref = section
    i = 0
    for j, fname in enumerate(files):
        if fname.startswith(pref):
            i = j
            break
    # Compute "current part" by counting suffix "-part\d+"
    # But since we treat each file as atomic, "next part" is just i+2 (1-based) for humans; we return next_part integer as (i+2)
    path = _chapter_dir(book_slug, chapter) / files[i]
    # section stem is the filename without extension
    stem = Path(files[i]).stem
    next_part = i + 2  # "next" as human 1-based index of the following file (not used heavily)
    return path, stem, next_part

def next_after_success(book_slug: str, chapter: int, current_stem: str) -> Tuple[int, str]:
    """Return next (chapter, section_stem). If we're at the end of chapter, advance to chapter+1, first file."""
    ch_idx = _load_chapter_index(book_slug, chapter)
    files = ch_idx.get("files") or []
    try:
        i = files.index(f"{current_stem}.txt")
    except ValueError:
        # If stem has "-partX", drop extension & match by stem
        matches = [k for k in files if k.startswith(current_stem)]
        if matches:
            i = files.index(matches[0])
        else:
            i = 0
    if i + 1 < len(files):
        # next file in same chapter
        next_stem = Path(files[i + 1]).stem
        return chapter, next_stem
    else:
        # first file of next chapter
        next_chapter = chapter + 1
        ch_idx2 = _load_chapter_index(book_slug, next_chapter)
        files2 = ch_idx2.get("files") or []
        if not files2:
            raise RuntimeError(f"No files in next chapter ch{next_chapter:02d}")
        return next_chapter, Path(files2[0]).stem
