PY ?= .venv/bin/python
RAW ?= archive/twcs/twcs.csv

.PHONY: setup test lint data silver

setup:
	uv venv --python 3.12 .venv
	uv pip install --python .venv -r requirements.txt -r requirements-dev.txt

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

data:
	$(PY) -m data.prepare --raw $(RAW) --out data/processed --card data/DATA_CARD.md

# Rebuild data/processed/silver_train.parquet from the committed labels + twcs.csv
silver: data
	$(PY) -m data.label_silver --rebuild
