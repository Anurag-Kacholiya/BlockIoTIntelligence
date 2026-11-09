#!/bin/zsh
# Reproduces every final task 3 result (RQ-11, AI-driven blockchain), sequentially so runs don't share CPU. Needs
# dataset v2 and its real_time models (final task 1) and Besu (scripts/setup_besu.py).
#   scripts/run_final_task3.sh            # everything (~1 h)
#   scripts/run_final_task3.sh --resume   # continue the live runs after an interruption (keeps the forecaster)
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
export BLOCKIOT_VIEW=real_time
if [[ "$1" != "--resume" ]]; then
  echo "== forecaster"; $PY scripts/train_forecaster.py
fi
echo "== offline sweep";  $PY scripts/run_ai_blockchain.py simulate
echo "== live runs";      $PY scripts/run_ai_blockchain.py run $1
echo "== figures";        $PY scripts/make_figures.py --set final_task3
echo FINAL_TASK3_DONE
