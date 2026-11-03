#!/bin/zsh
# Reproduces every final task 2 result (multi-node blockchain: 4 Besu validators, QBFT), sequentially so runs
# don't share CPU. Needs dataset v2 and its real_time models (final task 1) and Besu (scripts/setup_besu.py).
#   scripts/run_final_task2.sh            # everything (~1.5 h)
#   scripts/run_final_task2.sh --resume   # continue after an interruption (skips runs already recorded)
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
echo "== network check";               $PY scripts/run_multinode.py check
echo "== experiment groups T2.1-T2.4"; $PY scripts/run_multinode.py run $1
echo "== security on QBFT";            $PY scripts/run_security.py --rows 3000 --replay realistic --chain qbft
echo "== figures";                     $PY scripts/make_figures.py --set final_task2
echo FINAL_TASK2_DONE
