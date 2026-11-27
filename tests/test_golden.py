from pathlib import Path

import pandas as pd
import pytest

from agent.taxonomy import INTENTS
from data.september import dedupe_weak, read_golden_draft
from eval.sample_golden import SHEET_COLUMNS, compose

# ----------------------------------------------------------------------------- CSV repair


def test_read_golden_draft_repairs_unquoted_commas(tmp_path):
    path = tmp_path / "draft.csv"
    path.write_text(
        "case_id,intent,multi_intent,escalate,escalate_reason_code,annotator_confidence,notes\n"
        "1,other,False,False,,2,plain note\n"
        "2,other,False,False,,2,note, with, commas\n"
        '3,other,False,False,,3,"quoted, note"\n'
        "4,feature_complaint,False,False,,3,\n",
        encoding="utf-8",
    )
    df = read_golden_draft(path)
    assert len(df) == 4
    assert df.loc[1, "notes"] == "note, with, commas"
    assert df.loc[2, "notes"] == "quoted, note"
    assert df["repaired"].tolist() == [False, True, False, False]
    assert df.loc[1, "source_line"] == 3


def test_read_golden_draft_rejects_wrong_header(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("id,label\n1,other\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_golden_draft(path)


def test_dedupe_weak_keeps_last():
    recs = [
        {"case_id": "1", "intent": "other", "confidence": 0.3},
        {"case_id": 1, "intent": "other", "confidence": 0.6},
        {"case_id": "2", "intent": "playback_error", "confidence": 0.9},
    ]
    df = dedupe_weak(recs).set_index("case_id")
    assert len(df) == 2 and df.loc["1", "confidence"] == 0.6


# ----------------------------------------------------------------------------- sampler


def _fake_test(n=600):
    ids = [str(100000 + i) for i in range(n)]
    buckets = pd.Series([INTENTS[i % 15] for i in range(n)])  # nothing predicted `other`
    test = pd.DataFrame({"ticket_id": ids, "ticket_text": [f"t{i}" for i in range(n)]})
    return test, buckets


def test_compose_is_deterministic_and_unique():
    test, buckets = _fake_test()
    carried = set(test["ticket_id"].iloc[:30])
    a = compose(test, buckets, carried, seed=7, n_natural=100, min_per_intent=20)
    b = compose(test, buckets, carried, seed=7, n_natural=100, min_per_intent=20)
    c = compose(test, buckets, carried, seed=8, n_natural=100, min_per_intent=20)
    assert a["ticket_id"].tolist() == b["ticket_id"].tolist()
    assert a["ticket_id"].tolist() != c["ticket_id"].tolist()
    assert a["ticket_id"].is_unique


def test_compose_includes_all_carried_and_meets_quotas():
    test, buckets = _fake_test()
    carried = set(test["ticket_id"].iloc[:30])
    out = compose(test, buckets, carried, seed=7, n_natural=100, min_per_intent=20)
    assert carried <= set(out["ticket_id"])
    assert set(out.loc[out.subset == "carried", "ticket_id"]) == carried
    counts = out["bucket"].value_counts()
    assert all(counts.get(i, 0) >= 20 for i in INTENTS if i != "other")
    assert set(out["ticket_id"]) <= set(test["ticket_id"])  # only from the given split


def test_compose_respects_max_total():
    test, buckets = _fake_test()
    out = compose(test, buckets, set(), seed=7, n_natural=100, min_per_intent=50, max_total=250)
    assert len(out) == 250


# ----------------------------------------------------------------------------- real data

HAVE_DATA = Path("data/processed/test.parquet").exists() and Path(
    "reference/september/golden_set_labels_draft.csv"
).exists()


@pytest.mark.skipif(not HAVE_DATA, reason="needs data/processed and reference/september")
def test_real_golden_sample_is_test_only_and_reproducible(tmp_path, monkeypatch):
    import eval.sample_golden as sg

    monkeypatch.setattr(sg, "SHEET", tmp_path / "sheet.csv")
    monkeypatch.setattr(sg, "MANIFEST", tmp_path / "manifest.csv")
    g1 = sg.sample()
    sheet1 = (tmp_path / "sheet.csv").read_bytes()
    g2 = sg.sample()
    assert (tmp_path / "sheet.csv").read_bytes() == sheet1
    assert g1["ticket_id"].tolist() == g2["ticket_id"].tolist()

    splits = {s: set(pd.read_parquet(f"data/processed/{s}.parquet")["ticket_id"])
              for s in ["train", "val", "test"]}
    ids = set(g1["ticket_id"])
    assert ids <= splits["test"]
    assert not ids & (splits["train"] | splits["val"])
    assert 300 <= len(ids) <= 400

    sheet = pd.read_csv(tmp_path / "sheet.csv", dtype=str)
    assert sheet.columns.tolist() == SHEET_COLUMNS  # blind: no subset/carried/reply/silver
    assert sheet["gold_intent"].isna().all()


# ----------------------------------------------------------------------------- no leakage

HAVE_SPLITS = all(Path(f"data/processed/{s}.parquet").exists() for s in ["train", "val", "test"])


def _split_ids():
    return {s: set(pd.read_parquet(f"data/processed/{s}.parquet")["ticket_id"])
            for s in ["train", "val", "test"]}


@pytest.mark.skipif(not Path("data/processed/silver_train.parquet").exists() or not HAVE_SPLITS,
                    reason="needs data/processed/silver_train.parquet (built by --assemble)")
def test_silver_train_has_no_val_or_test_tickets():
    ids = _split_ids()
    silver = set(pd.read_parquet("data/processed/silver_train.parquet")["ticket_id"])
    assert silver <= ids["train"]
    assert not silver & ids["val"]
    assert not silver & ids["test"]


@pytest.mark.skipif(not (HAVE_SPLITS and HAVE_DATA), reason="needs processed splits + reference")
def test_silver_inputs_are_train_only():
    from data.label_silver import FEW_SHOT, load_inputs

    ids = _split_ids()
    train, weak, human, golden_ids = load_inputs()
    assert set(train["ticket_id"]) == ids["train"]
    assert set(weak["case_id"]) <= ids["train"]
    assert set(human["case_id"]) <= ids["train"]
    assert {tid for tid, _ in FEW_SHOT} <= ids["train"]


def test_committed_sheet_is_blind():
    sheet = Path("eval/golden_labeling.csv")
    if not sheet.exists():
        pytest.skip("labelling sheet not generated")
    header = sheet.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == SHEET_COLUMNS
    for leak in ["subset", "carried_over", "september_intent", "sampling_bucket",
                 "reference_reply", "silver_intent"]:
        assert leak not in header
