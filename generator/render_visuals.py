import sys, runpy, argparse
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()
    # visual_code is in the root/visuals_code.py
    plan_path = Path(f"out/{args.series}/latest/plan.json")
    code_file = plan_path.root / "visuals_code.py"
    if not code_file.exists():
        print("[render_visuals] ERROR: visuals_code.py not found at", code_file)
        sys.exit(1)

    # Run the generated code in-process (so it can pop up a VPython window or save output)
    try:
        runpy.run_path(str(code_file))
    except Exception as e:
        print("[render_visuals] ERROR running visuals_code.py:", e)
        sys.exit(2)

if __name__ == "__main__":
    main()
