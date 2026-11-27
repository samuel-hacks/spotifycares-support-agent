"""Build SpotifyCares (ticket, reply) pairs from twcs.csv, time-split them, write a data card.

Usage:
    python -m data.prepare --raw archive/twcs/twcs.csv --out data/processed --card data/DATA_CARD.md

One row per conversation:
    ticket      = the first customer tweet of the conversation (the thread root)
    brand_reply = the first SpotifyCares reply directly answering that root tweet
    thread      = every tweet in the conversation, in time order (for context)
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

import pandas as pd

BRAND = "SpotifyCares"
# @115888 is the anonymised main @Spotify account: it is mentioned ~14k times in
# tickets addressed to SpotifyCares but never authors a reply. Treated as a brand mention.
BRAND_MENTIONS = ("spotifycares", "115888")

DTYPES = {
    "tweet_id": str,
    "author_id": str,
    "inbound": str,
    "created_at": str,
    "text": str,
    "response_tweet_id": str,
    "in_response_to_tweet_id": str,
}
TIME_FMT = "%a %b %d %H:%M:%S %z %Y"

URL_RE = re.compile(r"https?://\S+|www\.\S+")
MENTION_RE = re.compile(r"@(\w+)")
WS_RE = re.compile(r"\s+")
# Agent signature at the end of a reply: " /NJ", "^JD", optionally followed by the DM-button link.
SIGNATURE_RE = re.compile(r"\s*[/^]\s?([A-Z]{1,3})\s*((?:https?://\S+\s*)*)$")
LEADING_MENTIONS_RE = re.compile(r"^(?:@\w+\s*)+")
PART_MARKER_RE = re.compile(r"^\d+\s*:\s*")


# --------------------------------------------------------------------------- text cleaning


def _sub_mention(match: re.Match) -> str:
    return "" if match.group(1).lower() in BRAND_MENTIONS else "@user"


def clean_ticket(text: str) -> str:
    """Normalise a customer tweet: drop brand mentions, URLs -> <URL>, users -> @user.

    Emojis are kept. BERTweet's own normaliser (@USER, HTTPURL) runs later, at training time.
    """
    if not isinstance(text, str):
        return ""
    text = html.unescape(text)
    text = URL_RE.sub("<URL>", text)
    text = MENTION_RE.sub(_sub_mention, text)
    return WS_RE.sub(" ", text).strip()


def split_signature(reply: str) -> tuple[str, str | None, bool]:
    """Split a brand reply into (body, agent_initials, has_trailing_link).

    The body keeps real URLs (the drafter's link check needs them) but loses the
    leading @recipient, any "1:" part marker, the signature and the trailing DM link.
    """
    if not isinstance(reply, str):
        return "", None, False
    text = html.unescape(reply).strip()
    text = LEADING_MENTIONS_RE.sub("", text)
    text = PART_MARKER_RE.sub("", text)
    sig, has_link = None, False
    m = SIGNATURE_RE.search(text)
    if m:
        sig = m.group(1)
        has_link = bool(m.group(2).strip())
        text = text[: m.start()]
    return WS_RE.sub(" ", text).strip(), sig, has_link


def clean_reply(body: str) -> str:
    """Model-facing version of a reply body: URLs -> <URL>, users -> @user."""
    text = URL_RE.sub("<URL>", body)
    text = MENTION_RE.sub(_sub_mention, text)
    return WS_RE.sub(" ", text).strip()


def has_letters(text: str) -> bool:
    stripped = text.replace("<URL>", "").replace("@user", "")
    return any(ch.isalpha() for ch in stripped)


# --------------------------------------------------------------------------- pair building


def load_raw(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=DTYPES)
    df["inbound"] = df["inbound"].str.lower().eq("true")
    df["created_at"] = pd.to_datetime(df["created_at"], format=TIME_FMT, utc=True)
    return df


def find_roots(parent: dict[str, str], ids) -> dict[str, str]:
    """Map each id to its conversation root by walking parent links (memoised)."""
    root: dict[str, str] = {}
    for tid in ids:
        path = []
        cur = tid
        while cur not in root:
            path.append(cur)
            nxt = parent.get(cur)
            if nxt is None or nxt in path:  # no parent in the data, or a cycle
                root[cur] = cur
                break
            cur = nxt
        r = root[cur]
        for p in path:
            root[p] = r
    return root


def build_pairs(df: pd.DataFrame, brand: str = BRAND) -> tuple[pd.DataFrame, dict]:
    """Return one (ticket, first direct brand reply) row per conversation, plus build stats."""
    stats: dict = {}
    known = set(df["tweet_id"])
    has_parent = df["in_response_to_tweet_id"].notna() & df["in_response_to_tweet_id"].isin(known)
    linked = df.loc[has_parent]
    parent = dict(zip(linked["tweet_id"], linked["in_response_to_tweet_id"], strict=True))

    brand_df = df[df["author_id"] == brand]
    stats["brand_replies"] = len(brand_df)

    # Only conversations touched by the brand matter; walk up from brand replies.
    roots_of_brand = find_roots(parent, brand_df["tweet_id"])
    conv_roots = set(roots_of_brand.values())

    # Root for every tweet so threads include customer follow-ups the brand did not answer.
    all_roots = find_roots(parent, df["tweet_id"])
    df = df.assign(conversation_id=df["tweet_id"].map(all_roots))
    conv = df[df["conversation_id"].isin(conv_roots)]

    by_id = df.set_index("tweet_id")
    root_rows = by_id.loc[by_id.index.intersection(list(conv_roots))]
    tickets = root_rows[root_rows["inbound"] & (root_rows["author_id"] != brand)]
    stats["conversations"] = len(conv_roots)
    stats["conversations_with_customer_root"] = len(tickets)

    direct = brand_df[brand_df["in_response_to_tweet_id"].isin(tickets.index)]
    first_reply = direct.sort_values("created_at").drop_duplicates("in_response_to_tweet_id")
    stats["conversations_with_direct_reply"] = len(first_reply)

    threads = {
        cid: [
            {"role": "brand" if a == brand else "customer", "text": t}
            for a, t in zip(g["author_id"], g["text"], strict=True)
        ]
        for cid, g in conv.sort_values("created_at").groupby("conversation_id")
    }

    t = tickets.loc[first_reply["in_response_to_tweet_id"]]
    pairs = pd.DataFrame(
        {
            "conversation_id": t.index.values,
            "ticket_id": t.index.values,
            "created_at": t["created_at"].values,
            "ticket_raw": t["text"].values,
            "reply_id": first_reply["tweet_id"].values,
            "reply_created_at": first_reply["created_at"].values,
            "reply_raw": first_reply["text"].values,
        }
    )
    pairs["ticket_text"] = pairs["ticket_raw"].map(clean_ticket)
    split = pairs["reply_raw"].map(split_signature)
    pairs["reply_text"] = split.map(lambda s: s[0])
    pairs["reply_signature"] = split.map(lambda s: s[1])
    pairs["reply_has_dm_link"] = split.map(lambda s: s[2])
    pairs["reply_clean"] = pairs["reply_text"].map(clean_reply)
    pairs["thread"] = pairs["conversation_id"].map(lambda c: json.dumps(threads.get(c, [])))
    pairs["thread_len"] = pairs["conversation_id"].map(lambda c: len(threads.get(c, [])))

    before = len(pairs)
    pairs = pairs[pairs["ticket_text"].map(has_letters) & pairs["reply_text"].str.len().gt(0)]
    stats["dropped_empty"] = before - len(pairs)

    before = len(pairs)
    pairs = pairs.sort_values("created_at").drop_duplicates("ticket_text", keep="first")
    stats["dropped_duplicates"] = before - len(pairs)
    stats["pairs"] = len(pairs)
    return pairs.reset_index(drop=True), stats


# --------------------------------------------------------------------------- split + language


def time_split(pairs: pd.DataFrame, train: float = 0.8, val: float = 0.1) -> pd.DataFrame:
    """Oldest `train` share -> train, next `val` -> val, newest rest -> test."""
    out = pairs.sort_values(["created_at", "ticket_id"]).reset_index(drop=True)
    n = len(out)
    n_train, n_val = int(n * train), int(n * val)
    out["split"] = ["train"] * n_train + ["val"] * n_val + ["test"] * (n - n_train - n_val)
    return out


def detect_language(texts: pd.Series, seed: int = 0) -> pd.Series:
    from langdetect import DetectorFactory, LangDetectException, detect

    DetectorFactory.seed = seed

    def _one(t: str) -> str:
        t = t.replace("<URL>", "").replace("@user", "").strip()
        try:
            return detect(t) if len(t) >= 3 else "unk"
        except LangDetectException:
            return "unk"

    return texts.map(_one)


# --------------------------------------------------------------------------- data card


def write_data_card(pairs: pd.DataFrame, stats: dict, path: str | Path, raw_path: str) -> None:
    lines = [
        "# Data card: SpotifyCares ticket/reply pairs",
        "",
        f"Source: Kaggle \"Customer Support on Twitter\" (`{Path(raw_path).name}`), "
        "brand account `SpotifyCares`. Built by `make data` (`data/prepare.py`).",
        "",
        "## How pairs were built",
        "",
        "- A ticket is the first customer tweet of a conversation (the thread root).",
        "- The paired reply is the first SpotifyCares tweet that answers that root directly.",
        "- Ticket text: brand mentions (`@SpotifyCares`, `@115888` = anonymised @Spotify) "
        "removed, URLs -> `<URL>`, other mentions -> `@user`, HTML entities unescaped, "
        "emojis kept.",
        "- Reply text: leading @recipient, `1:` part markers, agent signature (`/NJ`, `^JD`) "
        "and the trailing DM link removed. Real URLs are kept in `reply_text`; `reply_clean` "
        "has `<URL>`. The signature is stored in `reply_signature`.",
        "- Exact-duplicate tickets removed (earliest kept). Tickets with no letters dropped.",
        "- Time split on ticket `created_at`: oldest 80% train, next 10% val, newest 10% test.",
        "",
        "## Build funnel",
        "",
        "| step | count |",
        "|---|---:|",
    ]
    for k in [
        "brand_replies",
        "conversations",
        "conversations_with_customer_root",
        "conversations_with_direct_reply",
        "dropped_empty",
        "dropped_duplicates",
        "pairs",
    ]:
        lines.append(f"| {k} | {stats[k]:,} |")

    lines += ["", "## Splits", "", "| split | pairs | from | to |", "|---|---:|---|---|"]
    for name in ["train", "val", "test"]:
        s = pairs[pairs["split"] == name]
        lines.append(
            f"| {name} | {len(s):,} | {s['created_at'].min():%Y-%m-%d %H:%M} | "
            f"{s['created_at'].max():%Y-%m-%d %H:%M} |"
        )

    tw = pairs["ticket_text"].str.split().str.len()
    rw = pairs["reply_text"].str.split().str.len()
    lines += [
        "",
        "## Lengths",
        "",
        "| field | mean chars | mean words | median words | max words |",
        "|---|---:|---:|---:|---:|",
        f"| ticket_text | {pairs['ticket_text'].str.len().mean():.0f} | {tw.mean():.1f} | "
        f"{tw.median():.0f} | {tw.max()} |",
        f"| reply_text | {pairs['reply_text'].str.len().mean():.0f} | {rw.mean():.1f} | "
        f"{rw.median():.0f} | {rw.max()} |",
        "",
        f"- Replies with an agent signature: {pairs['reply_signature'].notna().mean():.1%} "
        f"({pairs['reply_signature'].nunique()} distinct initials)",
        f"- Replies ending in a DM link: {pairs['reply_has_dm_link'].mean():.1%}",
        f"- Conversations with more than two tweets: {(pairs['thread_len'] > 2).mean():.1%}",
        "",
        "## Language mix (langdetect on ticket_text, seed 0)",
        "",
        "| lang | share |",
        "|---|---:|",
    ]
    for lang, share in pairs["lang"].value_counts(normalize=True).head(10).items():
        lines.append(f"| {lang} | {share:.1%} |")

    lines += ["", "## Examples (random, seed 7)", ""]
    for _, r in pairs.sample(min(6, len(pairs)), random_state=7).iterrows():
        lines += [
            f"- **[{r['split']}] ticket:** {r['ticket_text']}",
            f"  **reply:** {r['reply_text']}",
        ]
    lines += [
        "",
        "## Known caveats",
        "",
        "- Twitter user IDs are anonymised in the source data, so `@user` replaces all handles.",
        "- Almost all data is from Oct to Dec 2017; a few older threads exist. The split is "
        "by time, so the test window is the most recent ~10% (see the Splits table).",
        "- The first reply is often a triage question (\"which device?\") rather than a fix; "
        "this matters for drafting and routing.",
        "",
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw", required=True, help="path to twcs.csv")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--card", default="data/DATA_CARD.md")
    args = ap.parse_args(argv)

    df = load_raw(args.raw)
    print(f"loaded {len(df):,} tweets")
    pairs, stats = build_pairs(df)
    pairs = time_split(pairs)
    print("detecting language ...")
    pairs["lang"] = detect_language(pairs["ticket_text"])

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in ["train", "val", "test"]:
        part = pairs[pairs["split"] == name].drop(columns="split")
        part.to_parquet(out / f"{name}.parquet", index=False)
        print(f"{name}: {len(part):,} -> {out / f'{name}.parquet'}")
    write_data_card(pairs, stats, args.card, args.raw)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
