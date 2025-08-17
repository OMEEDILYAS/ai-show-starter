import argparse
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    plan_path = sorted(Path(f"out/{args.series}").glob("ep_*/plan.json"))[-1]
    ep_dir = Path(plan_path).parent
    final = (ep_dir.parent / "final" / f"{ep_dir.name}.mp4")
    if not final.exists():
        raise SystemExit("no video produced")
    print("[validate] ok")

if __name__ == "__main__":
    main()
