# generator/fetch_stock.py
import argparse, os, json, random, re, sys, time
from pathlib import Path
import requests

# --- Simple keyword presets per series ---
KEYWORDS = {
    "ai_teacher": ["math", "matrix", "algebra", "equations", "geometry", "graphs", "numbers"],
    "ai_drama":   ["city night", "silhouette", "rain street", "moody b-roll", "neon"],
    "ai_memes":   ["colorful pattern", "abstract loop", "confetti", "pop art", "emoji"]
}

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name)[:80]

def pick_keywords(series: str, k: int = 3):
    base = KEYWORDS.get(series, KEYWORDS["ai_memes"])
    if len(base) <= k: return base
    return random.sample(base, k)

# -------- Pexels ----------
def pexels_search(api_key: str, query: str, per_page=10):
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": per_page}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def best_pexels_mp4(video_obj: dict):
    files = video_obj.get("video_files") or []
    # prefer vertical-ish and <=1080 width
    def score(f):
        w = f.get("width") or 0
        h = f.get("height") or 0
        vert = 1 if h >= w else 0
        ok = 1 if w <= 1080 else 0
        return (vert, ok, -abs((h or 0) - 1920), -abs((w or 0) - 1080))
    if not files: return None
    files.sort(key=score, reverse=True)
    return files[0].get("link")

# -------- Pixabay ----------
def pixabay_search(api_key: str, query: str, per_page=20):
    url = "https://pixabay.com/api/videos/"
    params = {"key": api_key, "q": query, "per_page": per_page, "safesearch": "true"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def best_pixabay_mp4(hit: dict):
    videos = hit.get("videos") or {}
    # prefer vertical-ish small/medium
    candidates = []
    for k, v in videos.items():
        url = v.get("url")
        w = v.get("width") or 0
        h = v.get("height") or 0
        if url:
            candidates.append((h >= w, w <= 1080, -abs(h-1920), -abs(w-1080), url))
    if not candidates: return None
    candidates.sort(reverse=True)
    return candidates[0][-1]

# -------- download ----------
def download(url: str, dest: Path) -> bool:
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1024*256):
                    if chunk: f.write(chunk)
        return True
    except Exception as e:
        print("[fetch] download failed:", url, e)
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--max_new", type=int, default=4)
    ap.add_argument("--per_query", type=int, default=8)
    args = ap.parse_args()

    series = args.series
    # workspace episode dirs (use now)
    out_dir = Path("out") / series
    plan_list = sorted(out_dir.glob("ep_*/plan.json"))
    if not plan_list:
        print(f"[fetch] no plan.json yet under out/{series}", file=sys.stderr)
        sys.exit(0)
    ep_dir = plan_list[-1].parent
    assets = ep_dir / "assets"
    ensure_dir(assets)

    # local library (persist in repo during run; workflow will push to gh-pages)
    local_lib_series = Path("assets/stock") / series
    ensure_dir(local_lib_series)

    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "").strip()

    if not pexels_key and not pixabay_key:
        print("[fetch] no stock API keys set; skipping fetch.")
        sys.exit(0)

    keywords = pick_keywords(series, 3)
    want = args.max_new
    downloaded = []

    # First try Pexels
    if pexels_key:
        for kw in keywords:
            if len(downloaded) >= want: break
            try:
                data = pexels_search(pexels_key, kw, per_page=args.per_query)
                for v in data.get("videos", []):
                    if len(downloaded) >= want: break
                    mp4 = best_pexels_mp4(v)
                    if not mp4: continue
                    name = sanitize(f"{series}_pexels_{v.get('id','vid')}.mp4")
                    dest = local_lib_series / name
                    if dest.exists():  # already have it
                        continue
                    if download(mp4, dest):
                        downloaded.append(dest)
                        print("[fetch] pexels ->", dest)
            except Exception as e:
                print("[fetch] pexels error:", e)

    # Then try Pixabay if still need more
    if pixabay_key and len(downloaded) < want:
        for kw in keywords:
            if len(downloaded) >= want: break
            try:
                data = pixabay_search(pixabay_key, kw, per_page=args.per_query)
                for hit in data.get("hits", []):
                    if len(downloaded) >= want: break
                    mp4 = best_pixabay_mp4(hit)
                    if not mp4: continue
                    name = sanitize(f"{series}_pixabay_{hit.get('id','vid')}.mp4")
                    dest = local_lib_series / name
                    if dest.exists():
                        continue
                    if download(mp4, dest):
                        downloaded.append(dest)
                        print("[fetch] pixabay ->", dest)
            except Exception as e:
                print("[fetch] pixabay error:", e)

    # Also stage into the current episode assets for immediate use
    staged = []
    for p in downloaded:
        tgt = assets / p.name
        try:
            tgt.write_bytes(p.read_bytes())
            staged.append(tgt)
        except Exception as e:
            print("[fetch] stage copy failed:", p, e)

    # Output list (optional)
    (assets / "fetched_list.txt").write_text(
        "\n".join(str(x) for x in staged), encoding="utf-8"
    )
    print(f"[fetch] done. new={len(downloaded)} staged={len(staged)}")

if __name__ == "__main__":
    main()
