import argparse, json
from pathlib import Path

def post_instagram(mp4_path, caption):
    print(f"[post] instagram -> {mp4_path}")
    return {"platform":"instagram","post_id":"fake_ig_123","url":"https://instagram.com/fake"}

def post_tiktok(mp4_path, caption):
    print(f"[post] tiktok -> {mp4_path}")
    return {"platform":"tiktok","post_id":"fake_tt_456","url":"https://tiktok.com/fake"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    plan_path = sorted(Path(f"out/{args.series}").glob("ep_*/plan.json"))[-1]
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    ep_dir = Path(plan_path).parent
    mp4 = ep_dir.parent / "final" / f"{ep_dir.name}.mp4"
    caption = f"{plan['title']} | #{args.series.replace('_','')}"

    results = []
    for p in plan["platforms"]:
        if p == "instagram":
            results.append(post_instagram(mp4, caption))
        elif p == "tiktok":
            results.append(post_tiktok(mp4, caption))

    (ep_dir / "posts.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("[post] done")

if __name__ == "__main__":
    main()
