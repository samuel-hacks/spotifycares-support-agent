# SpotifyCares support agent

An AI support agent for SpotifyCares, built on the Kaggle "Customer Support on Twitter" dataset. For each customer tweet it classifies intent, drafts a reply grounded in past SpotifyCares replies (with sources), and either auto-handles the ticket or escalates it with reason codes.

Work in progress. Day 1 of 6 (data prep and taxonomy) is done; see `DECISIONS.md` for progress and `docs/PROBLEM_STATEMENT.md` for the full spec.

## Quick start

```bash
make setup                                  # Python 3.12 venv via uv + deps
make data RAW=archive/twcs/twcs.csv         # -> data/processed/*.parquet + data/DATA_CARD.md
make test                                   # pytest
make lint                                   # ruff
```

Get `twcs.csv` from Kaggle ("Customer Support on Twitter", thoughtvector). It's gitignored.
