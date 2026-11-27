"""Load and link the September labels (reference/september/) to the new processed splits.

September `case_id` is the twcs `tweet_id` of the customer tweet, which is the
`ticket_id` here when that tweet is a conversation root that kept a direct reply.

Usage:
    python -m data.september            # prints the link report
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from agent.taxonomy import INTENTS

REF = Path("reference/september")
GOLDEN_DRAFT = REF / "golden_set_labels_draft.csv"
WEAK_RAW = REF / "weak_labels.jsonl"
WEAK_KEPT = [REF / "weak_train.jsonl", REF / "weak_val.jsonl"]

GOLDEN_COLUMNS = [
    "case_id",
    "intent",
    "multi_intent",
    "escalate",
    "escalate_reason_code",
    "annotator_confidence",
    "notes",
]

#: September label -> v2 label. The 14 old intents keep their names; `non_english` was
#: a pre-filter written into the intent column once and stays a pre-filter outcome.
#: Old `other` maps to `other` here, but those rows are flagged for re-verification
#: because v2 moved several of them (artist_creator, region, Wrapped, no-issue).
SEPTEMBER_TO_V2: dict[str, str] = {name: name for name in INTENTS if name not in {
    "artist_creator", "insufficient_context"}}
SEPTEMBER_TO_V2["non_english"] = "non_english"


#: Old golden rows whose correct label may change under taxonomy v2, for Vijay to
#: re-verify. The value is the v2 rule that touches the row and a suggested label;
#: it is a prompt for review, NOT a relabel. Old labels stay as they were.
V2_REVERIFY: dict[str, tuple[str, str]] = {
    # old `other` rows that v2 moves
    "688080": ("artist_creator added", "artist_creator"),
    "488799": ("artist_creator added", "artist_creator"),
    "620376": ("artist_creator vs content_availability", "content_availability"),
    "2739615": ("region -> content_availability", "content_availability"),
    "2786592": ("region -> content_availability", "content_availability"),
    "2726072": ("region -> content_availability", "content_availability"),
    "79401": ("region -> content_availability", "content_availability"),
    "501014": ("Spotify-made playlists -> playlist_issue", "playlist_issue"),
    "2981984": ("Spotify-made playlists -> playlist_issue", "playlist_issue"),
    "577400": ("Spotify-made playlists -> playlist_issue", "playlist_issue"),
    "2899847": ("Spotify-made playlists -> playlist_issue", "playlist_issue"),
    "2537578": ("insufficient_context label", "insufficient_context"),
    "647105": ("insufficient_context label", "insufficient_context"),
    "2492533": ("insufficient_context label", "insufficient_context"),
    "585115": ("insufficient_context label", "insufficient_context"),
    "699509": ("insufficient_context label", "insufficient_context"),
    "2295642": ("insufficient_context label", "insufficient_context"),
    "2578892": ("insufficient_context label", "insufficient_context"),
    "694034": ("insufficient_context label", "insufficient_context"),
    "575708": ("insufficient_context label", "insufficient_context"),
    # rows with another old label that a v2 definition now touches
    "2605006": ("Spotify-made playlists -> playlist_issue", "playlist_issue"),
    "526683": ("Spotify-made playlists -> playlist_issue", "playlist_issue"),
    "2722776": ("artist_creator added", "artist_creator"),
    "153788": ("artist_creator added", "artist_creator"),
    "1778489": ("insufficient_context label", "insufficient_context"),
    "574263": ("insufficient_context label", "insufficient_context"),
    "122825": ("insufficient_context label", "insufficient_context"),
    "2920680": ("insufficient_context label", "insufficient_context"),
}


def read_golden_draft(path: str | Path = GOLDEN_DRAFT) -> pd.DataFrame:
    """Read the golden draft CSV, repairing rows with unquoted commas in `notes`.

    The file has 7 columns; `notes` is last and some rows contain bare commas, which
    split it into extra fields. Extra fields are joined back into `notes` with ", ".
    `repaired` marks the rows that needed it and `source_line` is the 1-based file line.
    """
    records = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        if header != GOLDEN_COLUMNS:
            raise ValueError(f"unexpected header: {header}")
        n = len(GOLDEN_COLUMNS)
        for line_no, row in enumerate(reader, start=2):
            if not row:
                continue
            repaired = len(row) > n
            if repaired:
                row = row[: n - 1] + [",".join(row[n - 1 :])]
            elif len(row) < n:
                row = row + [""] * (n - len(row))
            records.append([*row, repaired, line_no])
    df = pd.DataFrame(records, columns=[*GOLDEN_COLUMNS, "repaired", "source_line"])
    df["notes"] = df["notes"].str.strip()
    return df


def read_jsonl(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def dedupe_weak(records: list[dict]) -> pd.DataFrame:
    """Keep the last entry per case_id (later runs supersede earlier ones)."""
    df = pd.DataFrame(records)
    df["case_id"] = df["case_id"].astype(str)
    return df.drop_duplicates("case_id", keep="last").reset_index(drop=True)


def load_processed(processed: str | Path = "data/processed") -> pd.DataFrame:
    parts = []
    for split in ["train", "val", "test"]:
        p = pd.read_parquet(Path(processed) / f"{split}.parquet")
        parts.append(p.assign(split=split))
    return pd.concat(parts, ignore_index=True)


def link(case_ids: pd.Series, processed: pd.DataFrame) -> pd.Series:
    """Map September case_ids to the split their ticket fell into ('' if unmatched)."""
    split_of = dict(zip(processed["ticket_id"], processed["split"], strict=True))
    return case_ids.astype(str).map(split_of).fillna("")


def main() -> None:
    proc = load_processed()

    gold = read_golden_draft()
    gold["split"] = link(gold["case_id"], proc)
    print(f"golden draft rows: {len(gold)} (repaired lines: "
          f"{gold.loc[gold.repaired, 'source_line'].tolist()})")
    print("golden split:", gold["split"].replace("", "unmatched").value_counts().to_dict())

    raw = read_jsonl(WEAK_RAW)
    weak = dedupe_weak(raw)
    kept = pd.concat([pd.DataFrame(read_jsonl(p)) for p in WEAK_KEPT], ignore_index=True)
    kept["case_id"] = kept["case_id"].astype(str)
    print(f"weak raw lines: {len(raw)}, unique case_ids: {len(weak)}, "
          f"September kept (train+val): {len(kept)} / unique {kept.case_id.nunique()}")
    only_dedup = set(weak.case_id) - set(kept.case_id)
    only_kept = set(kept.case_id) - set(weak.case_id)
    print(f"in deduped not kept: {len(only_dedup)}, in kept not deduped: {len(only_kept)}")


if __name__ == "__main__":
    main()
