#!/bin/zsh
# Reproduces every final task 1 result (dataset v2: real timestamps and real devices), sequentially so runs don't
# share CPU. Needs all 52 dataset files (make data) and tshark.
#   scripts/run_final_task1.sh               # everything (several hours: event extraction, training, LODO)
#   scripts/run_final_task1.sh --step8-only  # only the experiments re-run on the realistic replay (~30 min)
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
if [[ "$1" != "--step8-only" ]]; then
  echo "== tshark validation";        $PY scripts/validate_tshark_extraction.py
  echo "== events from the 24 pcaps"; $PY scripts/build_realistic_events.py
  echo "== dataset v2 + splits";      $PY scripts/build_realistic_dataset.py
  for v in real_time real_random; do
    echo "== train view $v";          BLOCKIOT_VIEW=$v $PY scripts/train_models.py
  done
  echo "== offline (splits A, B)";    $PY scripts/run_realistic_eval.py offline
  echo "== split C (LODO)";           $PY scripts/run_realistic_eval.py lodo
  echo "== replay, no blockchain";    $PY scripts/run_realistic_eval.py replay --rows 200000
  echo "== replay, Merkle batch";     $PY scripts/run_realistic_eval.py replay --rows 200000 --blockchain batch
fi
echo "== integrity under attack";     $PY scripts/run_integrity_accuracy.py --rows 10000 --mode batch --replay realistic
echo "== security experiment";        $PY scripts/run_security.py --rows 3000 --replay realistic
echo "== comparison + scaling";       $PY scripts/run_experiments.py --suite final_task1
echo "== figures";                    $PY scripts/make_figures.py --set final_task1
echo FINAL_TASK1_DONE
