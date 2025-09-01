import os, sys, json, argparse
from pathlib import Path
from openai import OpenAI

client = OpenAI()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()

    # Load narration transcript (or plan)
    plan_path = Path(f"out/{args.series}/latest/plan.json")
    if not plan_path.exists():
        print("[gen_visuals_code] ERROR: plan.json not found at", plan_path)
        sys.exit(1)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    narration_file = plan_path.parent / "narration.txt"
    narration = narration_file.read_text(encoding="utf-8") if narration_file.exists() else ""

    # Prompt LLM to produce Python code for visuals
    prompt = f"""
    You are an assistant that generates Python code for animations.
    Library: vpython (preferred for 3D vectors, arrows, rotating scenes).
    Narration: {narration}

    Generate short, self-contained Python code snippets that produce
    an animation matching the narration. Only output code, nothing else.
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You generate VPython code for visuals."},
                  {"role": "user", "content": prompt}],
        max_tokens=600,
    )

    code = resp.choices[0].message.content
    code_file = plan_path.parent / "visuals_code.py"
    code_file.write_text(code, encoding="utf-8")

    print(f"[gen_visuals_code] wrote {code_file}")

if __name__ == "__main__":
    main()