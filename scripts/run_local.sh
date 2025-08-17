#!/usr/bin/env bash
set -e
series=${1:-ai_teacher}
python planner/plan_next.py --series "$series"
python generator/gen_assets.py --series "$series"
python assembly/build_video.py --series "$series"
python assembly/validate_video.py --series "$series"
python publisher/post_all.py --series "$series"
