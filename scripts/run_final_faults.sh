#!/bin/zsh
# Reproduces every fault-tolerance result (add-on after final task 2; ADR Experiment F), sequentially so runs don't
# share CPU. Needs dataset v2 and its real_time models (final task 1) and Besu (scripts/setup_besu.py).
#   scripts/run_final_faults.sh            # everything (~40 min)
#   scripts/run_final_faults.sh --resume   # continue after an interruption (skips runs already recorded)
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
echo "== fault scenarios"; $PY scripts/run_faults.py $1
echo "== figures";         $PY scripts/make_figures.py --set final_faults
echo FINAL_FAULTS_DONE
