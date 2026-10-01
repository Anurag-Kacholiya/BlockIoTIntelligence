PY ?= python3

.PHONY: setup data data-essential verify-data test lint

setup:            ## install pinned dependencies
	$(PY) -m pip install -r requirements.txt

data:             ## download all 52 Edge-IIoTset files and write checksums + dataset card
	$(PY) scripts/download_edge_iiotset.py

data-essential:   ## only the selected ML/DNN CSVs + docs
	$(PY) scripts/download_edge_iiotset.py --essential

verify-data:      ## re-check every downloaded file against data/metadata/checksums.sha256
	$(PY) scripts/download_edge_iiotset.py --verify

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check src scripts tests
