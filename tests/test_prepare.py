import json

import pandas as pd
import pytest

from data.prepare import (
    build_pairs,
    clean_reply,
    clean_ticket,
    find_roots,
    has_letters,
    load_raw,
    split_signature,
    time_split,
)

# ----------------------------------------------------------------------------- cleaning


def test_clean_ticket_strips_brand_and_normalises():
    raw = "@SpotifyCares @115888 my app crashes 😭 see https://t.co/abc &amp; ask @98765"
    assert clean_ticket(raw) == "my app crashes 😭 see <URL> & ask @user"


def test_clean_ticket_brand_mention_case_insensitive():
    assert clean_ticket("@spotifycares hello") == "hello"


def test_clean_ticket_handles_non_string():
    assert clean_ticket(None) == ""


@pytest.mark.parametrize(
    "raw, body, sig, link",
    [
        (
            "@12345 Hey! Could you DM us your email? /AK https://t.co/ldFdZRiNAt",
            "Hey! Could you DM us your email?",
            "AK",
            True,
        ),
        ("@12345 Try restarting the app ^JD", "Try restarting the app", "JD", False),
        (
            "@12345 1: Thanks! Ideas get closed here: https://t.co/x /NQ",
            "Thanks! Ideas get closed here: https://t.co/x",
            "NQ",
            False,
        ),
        ("@12345 Got it, looking into it.", "Got it, looking into it.", None, False),
    ],
)
def test_split_signature(raw, body, sig, link):
    assert split_signature(raw) == (body, sig, link)


def test_split_signature_does_not_eat_words_in_body():
    body, sig, _ = split_signature("@1 Use iOS 11 or later /MT")
    assert body == "Use iOS 11 or later" and sig == "MT"


def test_clean_reply_masks_urls():
    assert clean_reply("Check https://t.co/x for @456") == "Check <URL> for @user"


def test_has_letters():
    assert not has_letters("<URL> @user 👍")
    assert has_letters("help <URL>")


# ----------------------------------------------------------------------------- pairs


def test_find_roots_walks_chain_and_handles_cycles():
    parent = {"c": "b", "b": "a", "x": "y", "y": "x"}
    roots = find_roots(parent, ["c", "b", "a", "x"])
    assert roots["c"] == roots["b"] == roots["a"] == "a"
    assert roots["x"] in {"x", "y"}


def _row(tid, author, inbound, ts, text, parent=None):
    return {
        "tweet_id": tid,
        "author_id": author,
        "inbound": "True" if inbound else "False",
        "created_at": ts,
        "text": text,
        "response_tweet_id": None,
        "in_response_to_tweet_id": parent,
    }


@pytest.fixture
def raw_csv(tmp_path):
    rows = [
        # conversation 1: root -> brand reply -> follow-up -> second brand reply
        _row("1", "111", True, "Tue Oct 31 10:00:00 +0000 2017",
             "@SpotifyCares app keeps crashing"),
        _row("2", "SpotifyCares", False, "Tue Oct 31 10:05:00 +0000 2017",
             "@111 Which device are you on? /AB", "1"),
        _row("3", "111", True, "Tue Oct 31 10:06:00 +0000 2017", "@SpotifyCares iPhone 8", "2"),
        _row("4", "SpotifyCares", False, "Tue Oct 31 10:10:00 +0000 2017",
             "@111 Try reinstalling /CD", "3"),
        # conversation 2: duplicate ticket text, later -> dropped as duplicate
        _row("5", "222", True, "Wed Nov 01 10:00:00 +0000 2017",
             "@SpotifyCares app keeps crashing"),
        _row("6", "SpotifyCares", False, "Wed Nov 01 10:01:00 +0000 2017", "@222 Hi! /EF", "5"),
        # conversation 3: root tweet only a link -> dropped as empty
        _row("7", "333", True, "Thu Nov 02 10:00:00 +0000 2017", "@SpotifyCares https://t.co/z"),
        _row("8", "SpotifyCares", False, "Thu Nov 02 10:01:00 +0000 2017", "@333 Hi! /GH", "7"),
        # conversation 4: unrelated brand, ignored
        _row("9", "444", True, "Fri Nov 03 10:00:00 +0000 2017", "@AppleSupport help"),
        _row("10", "AppleSupport", False, "Fri Nov 03 10:01:00 +0000 2017", "@444 sure", "9"),
        # conversation 5: valid, later in time
        _row("11", "555", True, "Sat Nov 04 10:00:00 +0000 2017",
             "@115888 I was charged twice &amp; want a refund"),
        _row("12", "SpotifyCares", False, "Sat Nov 04 10:02:00 +0000 2017",
             "@555 Sorry! Can you DM us? /IJ https://t.co/dm", "11"),
    ]
    path = tmp_path / "twcs_small.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_load_raw_types(raw_csv):
    df = load_raw(raw_csv)
    assert df["tweet_id"].dtype == object and df["tweet_id"].iloc[0] == "1"
    assert df["inbound"].dtype == bool
    assert str(df["created_at"].dt.tz) == "UTC"


def test_build_pairs(raw_csv):
    pairs, stats = build_pairs(load_raw(raw_csv))
    assert list(pairs["ticket_id"]) == ["1", "11"]
    first = pairs.iloc[0]
    assert first["ticket_text"] == "app keeps crashing"
    assert first["reply_text"] == "Which device are you on?"
    assert first["reply_signature"] == "AB"
    assert first["thread_len"] == 4
    assert [t["role"] for t in json.loads(first["thread"])] == [
        "customer", "brand", "customer", "brand"
    ]
    second = pairs.iloc[1]
    assert second["ticket_text"] == "I was charged twice & want a refund"
    assert bool(second["reply_has_dm_link"]) is True
    assert stats["dropped_duplicates"] == 1
    assert stats["dropped_empty"] == 1
    assert stats["pairs"] == 2


# ----------------------------------------------------------------------------- split


def test_time_split_is_ordered_and_disjoint():
    n = 100
    df = pd.DataFrame(
        {
            "ticket_id": [str(i) for i in range(n)],
            "created_at": pd.date_range("2017-10-01", periods=n, freq="h", tz="UTC")[::-1],
        }
    )
    out = time_split(df)
    counts = out["split"].value_counts()
    assert (counts["train"], counts["val"], counts["test"]) == (80, 10, 10)
    assert out.loc[out.split == "train", "created_at"].max() < out.loc[
        out.split == "val", "created_at"
    ].min()
    assert out.loc[out.split == "val", "created_at"].max() < out.loc[
        out.split == "test", "created_at"
    ].min()
