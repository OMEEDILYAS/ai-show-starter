# -*- coding: utf-8 -*-
"""
Simple cursor manager. Stores/reads: data/cursor.json

SCHEMA EXAMPLE
{
  "math_of_ML": { "chapter": 2, "section": "01-chapter", "part": 1 },
  "MAS":        { "chapter": 1, "section": "01-chapter", "part": 1 },
  "mixed":      { "series": "math_of_ML", "chapter": 2, "section": "01-chapter", "part": 1 }
}

USAGE
  from curriculum.cursor import get_cursor, set_cursor, advance_after_success
"""
import json
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
CURSOR_PATH = ROOT / "data" / "cursor.json"

def _init_if_missing() -> None:
    if not CURSOR_PATH.exists():
        CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
        CURSOR_PATH.write_text(json.dumps({
            "math_of_ML": {"chapter": 2, "section": "01-chapter", "part": 1},
            "MAS":        {"chapter": 1, "section": "01-chapter", "part": 1},
            "mixed":      {"series": "math_of_ML", "chapter": 2, "section": "01-chapter", "part": 1},
        }, indent=2), encoding="utf-8")

def read_all() -> Dict:
    _init_if_missing()
    return json.loads(CURSOR_PATH.read_text(encoding="utf-8"))

def write_all(data: Dict) -> None:
    CURSOR_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

def get_cursor(series: str) -> Dict:
    return read_all().get(series, {})

def set_cursor(series: str, chapter: int, section: str, part: int, *, mixed_series: Optional[str]=None) -> None:
    data = read_all()
    if series == "mixed":
        data["mixed"] = {"series": mixed_series or "math_of_ML", "chapter": chapter, "section": section, "part": part}
    else:
        data[series] = {"chapter": chapter, "section": section, "part": part}
    write_all(data)
