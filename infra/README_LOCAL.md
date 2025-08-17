Local run (Linux/Mac or Git Bash on Windows)
1) python -m venv .venv && source .venv/bin/activate
2) pip install -r infra/requirements.txt
3) bash scripts/run_local.sh ai_teacher

Windows PowerShell (no bash):
  python planner/plan_next.py --series ai_teacher
  python generator/gen_assets.py --series ai_teacher
  python assembly/build_video.py --series ai_teacher
  python assembly/validate_video.py --series ai_teacher
  python publisher/post_all.py --series ai_teacher
