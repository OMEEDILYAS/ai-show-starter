# curriculum/extract_unit.py
import argparse, json, os, re
from pathlib import Path

def read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def ensure_episode_dirs(series: str):
    series_dir = Path("out") / series
    eps = sorted(series_dir.glob("ep_*/plan.json"))
    if eps:
        ep_dir = eps[-1].parent
    else:
        ep_dir = series_dir / "ep_001"
        (ep_dir / "assets").mkdir(parents=True, exist_ok=True)
        # minimal plan so later steps don’t choke
        (ep_dir / "plan.json").write_text(json.dumps({"series": series}, indent=2), encoding="utf-8")
    (ep_dir / "assets").mkdir(parents=True, exist_ok=True)
    return ep_dir

def make_placeholder(series: str, ep_dir: Path):
    assets = ep_dir / "assets"
    # Try to infer theme from existing files (optional)
    title = (assets / "title.txt").read_text(encoding="utf-8").strip() if (assets / "title.txt").exists() else ""
    overlay = (assets / "overlay.txt").read_text(encoding="utf-8").strip() if (assets / "overlay.txt").exists() else ""
    hint = title or overlay or series.replace("_", " ").title()
    content = (
        f"# Placeholder Unit — {series}\n\n"
        f"This episode should focus on: **{hint}**.\n\n"
        "- Keep it concise (45–60s).\n"
        "- Use 1–2 concrete examples.\n"
        "- End with a teaser: what’s next.\n"
        "\n"
        "## Key points to cover\n"
        "1) Concept definition (own words)\n"
        "2) One practical/example application\n"
        "3) Mini recap + teaser\n"
    )
    (assets / "curriculum.txt").write_text(content, encoding="utf-8")
    print(f"[curriculum] wrote placeholder curriculum.txt for {series}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()
    series = args.series

    ep_dir = ensure_episode_dirs(series)
    assets = ep_dir / "assets"

    # Read manifest + progress (if exist)
    manifest = Path("curriculum") / "manifest.yaml"
    progress_p = Path("progress") / f"{series}.json"
    if not progress_p.exists():
        progress_p.parent.mkdir(parents=True, exist_ok=True)
        progress_p.write_text(json.dumps({"next_index": 0}, indent=2), encoding="utf-8")

    # Very light YAML parser for our simple structure (no PyYAML dependency)
    # Expected shape:
    # ai_teacher:
    #   - book: linear_algebra.pdf
    #     pages: 1-12
    #     title: Vectors & Geometry
    text = manifest.read_text(encoding="utf-8") if manifest.exists() else ""
    blocks = {}
    current = None
    for line in text.splitlines():
        if re.match(r"^\s*#", line):  # comment
            continue
        m = re.match(r"^([a-zA-Z0-9_]+):\s*$", line)
        if m:
            current = m.group(1)
            blocks[current] = []
            continue
        m = re.match(r"^\s*-\s*(.*)$", line)
        if current and m:
            # collect yaml-ish item lines until next dash/section
            item_line = m.group(1).strip()
            # simple key: value; key: value parser
            item = {}
            parts = [p.strip() for p in re.split(r"\s+(?=[a-zA-Z0-9_]+\s*:)", item_line)]
            # also support single key:value on first line
            parts = [item_line] if not parts else parts
            for p in parts:
                kv = p.split(":", 1)
                if len(kv) == 2:
                    k, v = kv[0].strip(), kv[1].strip().strip('"').strip("'")
                    item[k] = v
            blocks[current].append(item)

    series_items = blocks.get(series, [])
    prog = read_json(progress_p, {"next_index": 0})
    i = int(prog.get("next_index", 0))

    if not series_items or i >= len(series_items):
        # No manifest or out of items → write placeholder and exit gracefully
        make_placeholder(series, ep_dir)
        return

    # We have a manifest item; stage a short “reading brief” (not the raw book)
    it = series_items[i]
    title = it.get("title", f"Unit {i+1}")
    src = f"{it.get('book','(book?)')} {it.get('pages','')}".strip()
    brief = (
        f"# Reading Brief — {title}\n\n"
        f"Source: {src}\n\n"
        "Summarize the main ideas in your own words (no copying). "
        "Cover the definitions, one useful example, and an application. "
        "Keep the episode 45–60s and end with a teaser for the next item.\n"
    )
    (assets / "curriculum.txt").write_text(brief, encoding="utf-8")
    print(f"[curriculum] staged manifest unit {i+1}/{len(series_items)} for {series}")

if __name__ == "__main__":
    main()
