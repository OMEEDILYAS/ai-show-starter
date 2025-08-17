import argparse
from pathlib import Path

def build_dummy_video(assets_dir, out_mp4):
    out_mp4.write_bytes(b"FAKE_MP4")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    plan_path = sorted(Path(f"out/{args.series}").glob("ep_*/plan.json"))[-1]
    ep_dir = Path(plan_path).parent
    assets_dir = ep_dir / "assets"
    final_dir = ep_dir.parent / "final"
    final_dir.mkdir(exist_ok=True)
    out_mp4 = final_dir / f"{ep_dir.name}.mp4"

    build_dummy_video(assets_dir, out_mp4)
    print(f"[assemble] video at {out_mp4}")

if __name__ == "__main__":
    main()
