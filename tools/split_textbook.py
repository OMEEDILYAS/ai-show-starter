#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time splitter for textbook PDFs → plain-text curriculum chunks.
Run locally, commit the outputs so CI never parses PDFs.

WHAT IT DOES
  - Reads:   data/curriculum/<book_slug>/index.json   (your TOC + page_offset)
  - Reads:   data/textbooks/<book_slug>.pdf
  - Writes:  data/curriculum/<book_slug>/chXX/*.txt   (~300–500 words per chunk)
  - Writes:  data/curriculum/<book_slug>/chXX/chapter_index.json (ordered list)

USAGE
  python tools/split_textbook.py --book math_of_ML
  python tools/split_textbook.py --book MAS

DEPENDENCIES (local only)
  pip install pdfplumber

NOTES
  - page_offset is the offset from *printed* page numbers to *PDF index*:
      pdf_page = printed_page + page_offset
  - If a chapter has "sections" in index.json, we'll try to cut at those starts.
    If not, we simply chunk the chapter text by word count.
"""
import argparse, json, re, sys
from pathlib import Path
from typing import List, Dict, Tuple

try:
    import pdfplumber
except Exception as e:
    print("ERROR: pdfplumber not installed. Run: pip install pdfplumber", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]  # repo root guess
CURR = ROOT / "data" / "curriculum"
PDFS = ROOT / "data" / "textbooks"

# ---------------- Utility helpers ----------------

def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-") or "section"

def _normalize_text(s: str) -> str:
    # Lightweight cleanup: join hyphenated words, drop repeated whitespace, remove page headers/footers heuristically.
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Remove line endings that look like forced hyphenation: "lin-" "\n" "e"
    s = re.sub(r"(\w)-\n(\w)", r"\1\2", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def _read_index(book_slug: str) -> Dict:
    idx_path = CURR / book_slug / "index.json"
    if not idx_path.exists():
        raise FileNotFoundError(f"Missing TOC: {idx_path}")
    return json.loads(idx_path.read_text(encoding="utf-8"))

def _load_pdf(book_slug: str):
    pdf_path = PDFS / f"{book_slug}.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"Missing PDF: {pdf_path}")
    return pdfplumber.open(str(pdf_path))

def _pdf_text_between(pdf, pdf_start: int, pdf_end: int) -> str:
    """Extract text from inclusive pdf_start .. exclusive pdf_end (1-based index)."""
    # pdfplumber pages are 0-based internally, we accept 1-based
    chunks = []
    for pnum in range(pdf_start, pdf_end):
        if 1 <= pnum <= len(pdf.pages):
            page = pdf.pages[pnum - 1]
            text = page.extract_text() or ""
            chunks.append(text)
    return _normalize_text("\n".join(chunks))

def _chunk_by_words(text: str, target_min=300, target_max=500) -> List[str]:
    """Split text into chunks by word count (aim for 300–500 words per chunk)."""
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        # Take up to target_max words, but at least target_min (or whatever remains)
        end = min(i + target_max, len(words))
        if end - i < target_min and end < len(words):
            end = min(i + target_min, len(words))
        chunk = " ".join(words[i:end]).strip()
        if chunk:
            chunks.append(chunk)
        i = end
    return chunks or ([text] if text else [])

# ---------------- Split logic ----------------

def split_book(book_slug: str) -> None:
    toc = _read_index(book_slug)
    page_offset = int(toc.get("page_offset", 0))
    chapters = toc.get("chapters", [])

    with _load_pdf(book_slug) as pdf:
        # Pre-compute chapter start (printed → pdf index)
        chapter_starts = []
        for ch in chapters:
            printed = int(ch["start_page"])
            pdf_start = printed + page_offset
            chapter_starts.append((ch, pdf_start))

        # Determine chapter end pages by looking at the next chapter start
        for idx, (ch, pdf_start) in enumerate(chapter_starts):
            # pdf_end is next chapter's pdf_start, or len(pdf)+1 for the last chapter
            if idx + 1 < len(chapter_starts):
                pdf_end = chapter_starts[idx + 1][1]
            else:
                pdf_end = len(pdf.pages) + 1

            ch_num = int(ch["num"])
            ch_dir = CURR / book_slug / f"ch{ch_num:02d}"
            ch_dir.mkdir(parents=True, exist_ok=True)

            sections = ch.get("sections", [])
            chapter_index = []

            if sections:
                # Use section starts (printed pages) to slice chapter.
                # Convert each section printed page to pdf index and extract until next section/pdf_end.
                sec_entries: List[Tuple[str, int]] = []
                for sec in sections:
                    label = sec.get("label") or ""
                    title = sec.get("title") or ""
                    sec_printed = int(sec.get("start_page"))
                    sec_pdf_start = sec_printed + page_offset
                    sec_entries.append((f"{label} {title}".strip(), sec_pdf_start))
                # Append a sentinel for the end
                sec_entries_sorted = sorted(sec_entries, key=lambda x: x[1])
                for sidx, (sec_title, sec_start) in enumerate(sec_entries_sorted):
                    sec_end = sec_entries_sorted[sidx + 1][1] if sidx + 1 < len(sec_entries_sorted) else pdf_end
                    text = _pdf_text_between(pdf, sec_start, sec_end)
                    chunks = _chunk_by_words(text)
                    base = f"{sidx+1:02d}-{_slugify(sec_title) or 'section'}"
                    for j, chunk in enumerate(chunks, 1):
                        fname = f"{base}-part{j}.txt" if len(chunks) > 1 else f"{base}.txt"
                        (ch_dir / fname).write_text(chunk, encoding="utf-8")
                        chapter_index.append(fname)
            else:
                # No sections listed: slice the entire chapter, then auto-chunk by word count.
                text = _pdf_text_between(pdf, pdf_start, pdf_end)
                chunks = _chunk_by_words(text)
                base = "01-chapter"
                for j, chunk in enumerate(chunks, 1):
                    fname = f"{base}-part{j}.txt" if len(chunks) > 1 else f"{base}.txt"
                    (ch_dir / fname).write_text(chunk, encoding="utf-8")
                    chapter_index.append(fname)

            # Write a per-chapter index to keep ordering deterministic
            (ch_dir / "chapter_index.json").write_text(
                json.dumps({"chapter": ch_num, "files": chapter_index}, indent=2),
                encoding="utf-8",
            )
            print(f"[split] {book_slug} ch{ch_num:02d}: wrote {len(chapter_index)} files → {ch_dir}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True, help="Book slug: math_of_ML or MAS")
    args = ap.parse_args()
    split_book(args.book)

if __name__ == "__main__":
    main()
