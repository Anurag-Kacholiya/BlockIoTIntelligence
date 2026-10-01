#!/bin/zsh
# Reproduces every result used in the first project presentation (sequential, so runs don't share CPU).
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
if [[ "$1" != "--skip-full" ]]; then
  echo "== full-scale runs (200k events)";  $PY scripts/run_baseline.py --rows 200000
  $PY scripts/run_blockchain.py --mode batch --rows 200000
fi
echo "== comparison + scaling suite";     $PY scripts/run_experiments.py --suite presentation1
echo "== integrity under attack";         $PY scripts/run_integrity_accuracy.py --rows 10000 --mode batch
echo "== security experiment";            $PY scripts/run_security.py --rows 3000
echo PRESENTATION1_DONE
