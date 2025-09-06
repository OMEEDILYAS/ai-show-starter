# generator/render_visuals.py
# PURPOSE: execute the generated visuals code for the newest episode.
# It looks under out/<series>/latest/assets/visuals_code.py first (where the
# generator writes it), then falls back to out/<series>/latest/visuals_code.py
# if a copy was made there by the workflow step.

import sys, runpy, argparse
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    root = Path("out") / args.series / "latest"
    plan_path = root / "plan.json"
    # Prefer the assets/ location (generator output)
    code_file = root / "assets" / "visuals_code.py"
    if not code_file.exists():
        # Fallback to flat location if the workflow copied it here
        alt = root / "visuals_code.py"
        if alt.exists():
            code_file = alt

    if not code_file.exists():
        print("[render_visuals] ERROR: visuals_code.py not found at", code_file)
        print("[render_visuals] Searched:", root / "assets" / "visuals_code.py", "and", root / "visuals_code.py")
        sys.exit(1)

    try:
        runpy.run_path(str(code_file))
    except Exception as e:
        print("[render_visuals] ERROR running visuals_code.py:", e)
        sys.exit(2)

if __name__ == "__main__":
    main()
