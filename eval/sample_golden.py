"""Sample the golden set from the TEST split and export a blind labelling sheet.

Usage:
    python -m eval.sample_golden sample   # -> eval/golden_labeling.csv + manifest
    python -m eval.sample_golden build    # filled sheet + manifest -> eval/golden.jsonl

Composition (all from the test split, fixed seed):
    carried     the September golden rows that fall in the test window (blind, for
                self-agreement: September label vs new label, ~2.5 months apart)
    natural     uniform random draw from test: true class priors
    stratified  top-up so every intent has at least MIN_PER_INTENT tickets

Stratification uses a throwaway TF-IDF + LogReg trained on train labels that already
exist (human, reused, rule). Its predicted bucket only decides WHICH tickets get
sampled; it is never written to the labelling sheet, so labelling stays blind and
silver-vs-gold agreement means something.

The labelling sheet is shuffled and carries no subset / carried_over / reference reply
columns; those live in the manifest, which Vijay doesn't open while labelling.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from agent.taxonomy import ACTIONS, ESCALATION_REASON_CODES, INTENTS

SEED = 2026
N_NATURAL = 150
MIN_PER_INTENT = 22
MIN_TOTAL, MAX_TOTAL = 300, 400

PROCESSED = Path("data/processed")
SHEET = Path("eval/golden_labeling.csv")
MANIFEST = Path("data/interim/golden_manifest.csv")
GOLDEN = Path("eval/golden.jsonl")

SHEET_COLUMNS = [
    "row",
    "ticket_id",
    "text",
    "text_raw",
    "gold_intent",
    "multi_intent",
    "gold_route",
    "gold_reason",
    "annotator_confidence",
    "notes",
]
ROUTES = ["auto", "clarify", "escalate"]


def sampling_buckets(train_labels: pd.DataFrame, test: pd.DataFrame, seed: int = SEED) -> pd.Series:
    """Predict a coarse intent bucket for each test ticket (sampling aid only)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    x = vec.fit_transform(train_labels["ticket_text"])
    clf = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed)
    clf.fit(x, train_labels["label"])
    return pd.Series(clf.predict(vec.transform(test["ticket_text"])), index=test.index)


def compose(
    test: pd.DataFrame,
    buckets: pd.Series,
    carried_ids: set[str],
    seed: int = SEED,
    n_natural: int = N_NATURAL,
    min_per_intent: int = MIN_PER_INTENT,
    max_total: int = MAX_TOTAL,
) -> pd.DataFrame:
    """Pick golden tickets from `test`. Returns test rows plus `subset` and `bucket`."""
    rng = np.random.default_rng(seed)
    test = test.assign(bucket=buckets)
    carried = test[test["ticket_id"].isin(carried_ids)].assign(subset="carried")
    rest = test[~test["ticket_id"].isin(carried_ids)]

    nat_idx = rng.choice(rest.index.to_numpy(), size=min(n_natural, len(rest)), replace=False)
    natural = rest.loc[sorted(nat_idx)].assign(subset="natural")
    rest = rest.drop(index=nat_idx)

    chosen = pd.concat([carried, natural])
    picks = []
    budget = max_total - len(chosen)
    for intent in INTENTS:
        need = min_per_intent - int((chosen["bucket"] == intent).sum())
        pool = rest[rest["bucket"] == intent]
        k = max(0, min(need, len(pool), budget))
        if k:
            idx = rng.choice(pool.index.to_numpy(), size=k, replace=False)
            picks.append(rest.loc[sorted(idx)])
            budget -= k
    stratified = pd.concat(picks).assign(subset="stratified") if picks else rest.iloc[:0]
    out = pd.concat([chosen, stratified])
    assert out["ticket_id"].is_unique
    return out


def load_train_labels() -> pd.DataFrame:
    from data.label_silver import load_inputs, plan_sources

    train, weak, human, _ = load_inputs()
    plan = plan_sources(train, weak, human)
    plan = plan[plan["source"].isin(["human", "reused", "rule", "rule_override"])]
    return plan.merge(train, on="ticket_id").rename(columns={"silver_intent": "label"})


def sample(seed: int = SEED) -> pd.DataFrame:
    from data.september import read_golden_draft

    test = pd.read_parquet(PROCESSED / "test.parquet").reset_index(drop=True)
    old = read_golden_draft()
    carried_ids = set(old["case_id"]) & set(test["ticket_id"])

    buckets = sampling_buckets(load_train_labels(), test, seed)
    golden = compose(test, buckets, carried_ids, seed)
    assert MIN_TOTAL <= len(golden) <= MAX_TOTAL, f"golden size {len(golden)} outside 300-400"

    # Shuffle so carried rows are mixed in, then number the rows for the labeller.
    golden = golden.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    golden["row"] = np.arange(1, len(golden) + 1)
    golden["carried_over"] = golden["subset"].eq("carried")
    old_label = dict(zip(old["case_id"], old["intent"], strict=True))
    golden["september_intent"] = golden["ticket_id"].map(old_label)

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    golden[
        ["row", "ticket_id", "subset", "carried_over", "september_intent", "bucket",
         "reply_text", "created_at"]
    ].rename(columns={"reply_text": "reference_reply", "bucket": "sampling_bucket"}).to_csv(
        MANIFEST, index=False
    )

    sheet = golden.rename(columns={"ticket_text": "text", "ticket_raw": "text_raw"})
    for col in ["gold_intent", "multi_intent", "gold_route", "gold_reason",
                "annotator_confidence", "notes"]:
        sheet[col] = ""
    sheet[SHEET_COLUMNS].to_csv(SHEET, index=False)
    return golden


def build(sheet_path: Path = SHEET, manifest_path: Path = MANIFEST, out: Path = GOLDEN) -> int:
    """Validate the filled sheet and write eval/golden.jsonl. Returns the row count."""
    sheet = pd.read_csv(sheet_path, dtype=str, keep_default_na=False)
    man = pd.read_csv(manifest_path, dtype=str, keep_default_na=False)
    df = sheet.merge(man.drop(columns=["row"]), on="ticket_id", how="left", validate="1:1")
    errors = []
    for _, r in df.iterrows():
        if r["gold_intent"] not in INTENTS and r["gold_intent"] != "non_english":
            errors.append(f"row {r['row']}: gold_intent {r['gold_intent']!r}")
        if r["gold_route"] not in ROUTES:
            errors.append(f"row {r['row']}: gold_route {r['gold_route']!r}")
        reasons = [x.strip() for x in r["gold_reason"].split(";") if x.strip()]
        bad = [x for x in reasons if x not in ESCALATION_REASON_CODES]
        if bad:
            errors.append(f"row {r['row']}: gold_reason {bad}")
    if errors:
        raise ValueError("labelling sheet has problems:\n" + "\n".join(errors[:30]))
    with open(out, "w", encoding="utf-8") as f:
        for _, r in df.iterrows():
            f.write(json.dumps({
                "ticket_id": r["ticket_id"],
                "text": r["text"],
                "gold_intent": r["gold_intent"],
                "multi_intent": r["multi_intent"].lower() == "true",
                "gold_route": r["gold_route"],
                "gold_reason": [x.strip() for x in r["gold_reason"].split(";") if x.strip()],
                "annotator_confidence": r["annotator_confidence"],
                "reference_reply": r["reference_reply"],
                "notes": r["notes"],
                "subset": r["subset"],
                "carried_over": r["carried_over"] == "True",
                "september_intent": r["september_intent"] or None,
            }, ensure_ascii=False) + "\n")
    return len(df)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "build"])
    args = ap.parse_args(argv)
    if args.cmd == "build":
        print(f"wrote {GOLDEN}: {build()} rows")
        return
    g = sample()
    print(f"golden sample: {len(g)} test tickets -> {SHEET} (blind), manifest {MANIFEST}")
    print("subset:", g["subset"].value_counts().to_dict())
    print("\nsampling bucket counts (aid only, not shown to the labeller):")
    print(pd.crosstab(g["bucket"], g["subset"]).reindex(INTENTS).fillna(0).astype(int).to_string())
    assert set(ACTIONS) == {"auto_handle", "clarify", "escalate"}


if __name__ == "__main__":
    main()
