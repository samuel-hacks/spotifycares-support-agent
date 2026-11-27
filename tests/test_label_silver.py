import json
import math

import pandas as pd
import pytest

from agent.taxonomy import INTENT_PRIORITY, INTENTS, resolve_primary_intent, validate
from data.label_silver import (
    FEW_SHOT,
    LABEL_COLUMNS,
    PREFILTER_RULE,
    REUSE_CHECK_LOW,
    RULES,
    apply_reuse_filter,
    apply_rules,
    build_messages,
    build_silver_train,
    label_confidence,
    label_with_llm,
    parse_reply,
    plan_sources,
    select_for_training,
    word_count,
)

# ----------------------------------------------------------------------------- taxonomy


def test_taxonomy_is_consistent():
    validate()
    assert len(INTENTS) == 16
    assert INTENT_PRIORITY.index("artist_creator") + 1 == 13
    assert INTENT_PRIORITY[-2:] == ["insufficient_context", "other"]


def test_resolve_primary_intent_is_mechanical():
    assert resolve_primary_intent(["playlist_issue", "account_compromise"]) == "account_compromise"
    with pytest.raises(ValueError):
        resolve_primary_intent(["not_a_label"])


# ----------------------------------------------------------------------------- rules


@pytest.mark.parametrize(
    "text, intent, rule",
    [
        ("hi", "insufficient_context", PREFILTER_RULE),
        ("read dm <URL> @user", "insufficient_context", PREFILTER_RULE),
        ("my account was hacked and they changed the email", "account_compromise",
         "account_compromise_hacked"),
        ("someone changed my password last night", "account_compromise",
         "account_compromise_hacked"),
        ("I got charged twice this month", "billing_charge_dispute", "billing_double_charge"),
        ("why is Clubmix 2007 not on spotify", "content_availability", "content_not_on_spotify"),
        ("when is #reputation coming", "content_availability", "content_not_on_spotify"),
        ("how long does a verification request on Spotify for Artists take?", "artist_creator",
         "artist_creator_s4a"),
        ("lost all my related artists on my artist page", "artist_creator",
         "artist_creator_own_profile"),
        ("uploaded my single through distrokid and it went to another artist", "artist_creator",
         "artist_creator_distribution"),
        ("when will we get our Top Songs of 2017 playlist?", "playlist_issue",
         "playlist_wrapped"),
    ],
)
def test_rules_fire(text, intent, rule):
    got = apply_rules(text)
    assert got is not None and got[0] == intent and got[1] == rule


@pytest.mark.parametrize(
    "text",
    [
        # false positives found while hand-checking hits
        "Why is “wrapped” by George Strait off of spotify? classics",
        "can you help me get my songs on my iPod and keep them on my computer",
        "I have a family plan question about adding my sister please",  # family rule was dropped
        "my app keeps crashing every time I open it on android",
    ],
)
def test_rules_do_not_fire(text):
    got = apply_rules(text)
    assert got is None or got[1] not in {"playlist_wrapped", "artist_creator_distribution"}
    if "crashing" in text or "family" in text:
        assert got is None


def test_rule_conflict_uses_intent_priority():
    # compromise (rank 1) beats content (rank 11)
    got = apply_rules("my account got hacked and now reputation is not on spotify for me")
    assert got[0] == "account_compromise"


def test_word_count_ignores_placeholders_and_symbols():
    assert word_count("@user <URL> 👍 !!") == 0
    assert word_count("please help me") == 3


def test_every_rule_targets_a_real_intent():
    assert all(r.intent in INTENTS for r in RULES)
    names = [r.name for r in RULES]
    assert len(names) == len(set(names))


# ----------------------------------------------------------------------------- LLM parsing


def test_parse_reply():
    assert parse_reply('{"intent": "playlist_issue"}') == "playlist_issue"
    assert parse_reply('{"intent": "made_up"}') is None
    assert parse_reply("not json") is None
    assert parse_reply('{"label": "other"}') is None


def test_label_confidence_sums_label_tokens_only():
    content = '{"intent": "playlist_issue"}'
    toks = [("{", -5.0), ('"intent', -3.0), ('": "', -1.0), ("play", math.log(0.5)),
            ("list_issue", math.log(0.8)), ('"}', -4.0)]
    logprobs = [{"token": t, "logprob": lp} for t, lp in toks]
    assert "".join(t for t, _ in toks) == content
    assert label_confidence(content, logprobs) == pytest.approx(0.4, abs=1e-4)


def test_label_confidence_rejects_misaligned_tokens():
    assert label_confidence('{"intent": "other"}', [{"token": "x", "logprob": -1}]) is None


def test_build_messages_has_few_shot_pairs():
    msgs = build_messages("my app crashed", [("ex text", "app_platform_bug")])
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": "ex text"}
    assert json.loads(msgs[2]["content"]) == {"intent": "app_platform_bug"}
    assert msgs[-1] == {"role": "user", "content": "my app crashed"}


def test_few_shot_labels_cover_every_intent():
    assert {intent for _, intent in FEW_SHOT} == set(INTENTS)


class FakeClient:
    model = "fake:1b"

    def __init__(self):
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        content = '{"intent": "feature_complaint"}'
        return content, [{"token": content, "logprob": math.log(0.9)}]


def test_llm_cache_resumes_without_relabelling(tmp_path):
    tickets = pd.DataFrame({"ticket_id": ["1", "2"], "ticket_text": ["add lyrics", "sleep timer"]})
    cache_path = tmp_path / "cache.jsonl"
    client = FakeClient()
    recs = label_with_llm(tickets, client, [], {}, cache_path)
    assert client.calls == 2 and all(r["intent"] == "feature_complaint" for r in recs)

    from data.label_silver import load_cache

    client2 = FakeClient()
    label_with_llm(tickets, client2, [], load_cache(cache_path), cache_path)
    assert client2.calls == 0


# ----------------------------------------------------------------------------- source plan


def test_plan_sources_precedence():
    train = pd.DataFrame({
        "ticket_id": ["h", "o", "r", "k", "l"],
        "ticket_text": [
            "my account was hacked",                 # human beats rule
            "how long for Spotify for Artists verification?",  # v2 rule overrides reused
            "my playlists are gone",                 # reused
            "I was charged twice",                   # rule
            "the shuffle button looks weird today",  # llm
        ],
    })
    weak = pd.DataFrame({"case_id": ["o", "r"], "intent": ["other", "playlist_issue"],
                         "confidence": [0.9, 0.8]})
    human = pd.DataFrame({"case_id": ["h"], "intent": ["account_compromise"]})
    plan = plan_sources(train, weak, human).set_index("ticket_id")
    assert plan.loc["h", "source"] == "human"
    assert plan.loc["o", "source"] == "rule_override"
    assert plan.loc["o", "silver_intent"] == "artist_creator"
    assert plan.loc["r", "source"] == "reused"
    assert plan.loc["k", "source"] == "rule"
    assert plan.loc["l", "source"] == "llm"


# ----------------------------------------------------------------------------- reuse filter


def _rec(intent, conf):
    return {"intent": intent, "confidence": conf, "model": "fake:1b", "prompt_version": "v"}


def test_reuse_filter_drops_low_agreement_disagreements():
    labels = pd.DataFrame({
        "ticket_id": ["a", "b", "c", "d", "e", "f"],
        "silver_intent": ["playback_error", "playback_error", "content_availability",
                          "feature_complaint", "playback_error", "account_compromise"],
        "confidence": [0.8] * 6,
        "source": ["reused", "reused", "reused", "reused", "reused", "human"],
        "model": ["qwen3:14b"] * 5 + [None],
        "prompt_version": ["september"] * 5 + [None],
    })
    llm = {
        "a": _rec("playback_error", 0.9),     # agrees -> stays reused
        "b": _rec("app_platform_bug", 0.99),  # disagrees, low intent -> dropped
        "c": _rec("playlist_issue", 0.99),    # disagrees but intent >= 0.75 -> stays
        # d: no LLM label -> stays
        "e": _rec("feature_complaint", 0.7),  # disagrees but few-shot ticket -> stays
        "f": _rec("playlist_issue", 0.99),    # human -> never touched
    }
    out = apply_reuse_filter(labels, llm, keep={"e"}).set_index("ticket_id")
    assert "playback_error" in REUSE_CHECK_LOW and "content_availability" not in REUSE_CHECK_LOW
    assert out.loc["a", "source"] == "reused"
    assert out.loc["b", "source"] == "dropped_disagreement"
    # the reused label stays for auditing; the LLM label is not copied in
    assert out.loc["b", "silver_intent"] == "playback_error"
    assert out.loc["b", "model"] == "qwen3:14b"
    assert (out.loc[["c", "d", "e"], "source"] == "reused").all()
    assert out.loc["f", "source"] == "human"
    assert out.loc["f", "silver_intent"] == "account_compromise"


def test_select_for_training_applies_cutoff_and_drops():
    labels = pd.DataFrame({
        "ticket_id": list("abcdef"),
        "silver_intent": ["other"] * 6,
        "confidence": [0.95, 0.7, 0.5, 0.4, 1.0, 0.95],
        "source": ["llm", "llm", "reused", "rule", "human", "dropped_disagreement"],
    })
    assert select_for_training(labels, 0.8)["ticket_id"].tolist() == ["a", "c", "d", "e"]
    assert select_for_training(labels, 0.6)["ticket_id"].tolist() == ["a", "b", "c", "d", "e"]


def test_build_silver_train_joins_text_and_rejects_unknown_ids():
    labels = pd.DataFrame({"ticket_id": ["2", "1"], "silver_intent": ["other", "other"],
                           "confidence": [0.5, 1.0], "source": ["llm", "human"],
                           "model": ["m", None], "prompt_version": ["v", None]})
    train = pd.DataFrame({"ticket_id": ["1", "2", "3"], "ticket_text": ["x", "y", "z"]})
    out = build_silver_train(labels, train)
    assert out.columns.tolist() == [*LABEL_COLUMNS, "ticket_text"]
    assert out["ticket_id"].tolist() == ["1", "2"] and out["ticket_text"].tolist() == ["x", "y"]
    with pytest.raises(ValueError):
        build_silver_train(labels.assign(ticket_id=["9", "1"]), train)

