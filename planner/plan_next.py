import json, argparse, time, pandas as pd # took out yml to see if workflow will run
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(open("config/series.yaml", "r", encoding="utf-8"))
    s = cfg["series"][args.series]

    season = json.load(open("data/season.json", "r", encoding="utf-8"))
    ep = season["next_episode"]

    topic = {"slug": f"ep{ep:03d}", "title": "Auto topic", "notes": ""}
    if s.get("topic_source"):
        df = pd.read_csv(s["topic_source"])
        idx = (ep - 1) % len(df)
        topic = df.iloc[idx].to_dict()

    outdir = Path(f"out/{args.series}/ep_{ep:03d}")
    outdir.mkdir(parents=True, exist_ok=True)
    plan = {
        "series": args.series,
        "episode": ep,
        "title": topic.get("title"),
        "slug": topic.get("slug"),
        "notes": topic.get("notes"),
        "aspect_ratio": s["aspect_ratio"],
        "target_len_sec": s["target_len_sec"],
        "platforms": s["platforms"],
        "ts_planned": int(time.time())
    }
    (outdir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    season["next_episode"] = ep + 1
    json.dump(season, open("data/season.json","w", encoding="utf-8"))

    print(f"[plan] planned {args.series} ep {ep:03d}")

if __name__ == "__main__":
    main()
