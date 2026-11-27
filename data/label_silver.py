"""Silver intent labels for the TRAIN split (taxonomy v2).

Precedence per ticket, highest first:
    human         September golden rows demoted to train (minus the ones awaiting re-verification)
    rule_override a high-precision v2 rule fired on a ticket that had a reused label
    reused        September qwen3:14b weak label (non-`other`, confidence >= 0.6)
    rule          a high-precision keyword rule
    llm           local LLM via Ollama (strict prompt, few-shot from TRAIN only)

Usage:
    python -m data.label_silver --pilot 50                # time + sanity check, LLM pool
    python -m data.label_silver --check-reused 200        # new prompt vs reused labels
    python -m data.label_silver --run [--limit N]         # label the LLM pool (cached, resumable)
    python -m data.label_silver --assemble                # write data/processed/silver_train.parquet

LLM results are cached in data/interim/silver_llm_cache.jsonl keyed by
(ticket_id, model, prompt_version), so an interrupted run resumes without relabelling.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from agent.taxonomy import INTENT_PRIORITY, INTENTS, MAX_WORDS_INSUFFICIENT

PROMPT_VERSION = "silver-v4"
SEED = 13
PROCESSED = Path("data/processed")
CACHE = Path("data/interim/silver_llm_cache.jsonl")
OUT = PROCESSED / "silver_train.parquet"
RULE_CONFIDENCE = 0.95

# --------------------------------------------------------------------------- rules


@dataclass(frozen=True)
class Rule:
    name: str
    intent: str
    pattern: re.Pattern
    overrides_reused: bool = False  # v2 rules: the old teacher didn't know these labels


def _r(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


#: High-precision rules only. Kept if agreement with existing labels was >= 0.90 on
#: train (account_compromise 0.98, billing 0.95, content 0.91), or, for v2 labels the
#: old teacher never had, if hand-checked hits looked right (see DECISIONS.md).
RULES: list[Rule] = [
    Rule("artist_creator_s4a", "artist_creator", _r(r"spotify for artists|\bs4a\b"), True),
    Rule(
        "artist_creator_own_profile",
        "artist_creator",
        _r(
            r"\bmy (?:artist (?:page|profile|account)|verified artist)"
            r"|\bverif(?:y|ied|ication)\b.{0,30}\bartist|\bartist\b.{0,30}\bverif"
        ),
        True,
    ),
    Rule(
        "artist_creator_distribution",
        "artist_creator",
        _r(
            r"distrokid|cd ?baby|tunecore|\baggregator\b|\bdistributor\b"
            r"|\bupload(?:ed)? (?:my|our|a) (?:new )?(?:song|single|music|track|album|ep)\b"
            r".{0,60}\b(?:another|other|different|wrong) (?:artist|band|dude|page|profile)"
        ),
        True,
    ),
    Rule(
        "playlist_wrapped",
        "playlist_issue",
        _r(
            r"top songs (?:of |from )?2017|year in mus|spotify wrapped|#spotifywrapped"
            r"|2017 wrapped|wrapped 2017|end of (?:the )?year playlist|year[- ]end playlist"
        ),
        True,
    ),
    Rule(
        "account_compromise_hacked",
        "account_compromise",
        _r(
            r"\b(?:account|acct|spotify)\b.{0,25}\b(?:hacked|stolen|compromised)\b"
            r"|\bhacked (?:my|into my)\b"
            r"|\bsomeone\b.{0,30}\b(?:hacked|is using|using my|changed (?:my|the) (?:email|password))"
        ),
    ),
    Rule(
        "billing_double_charge",
        "billing_charge_dispute",
        _r(
            r"charged (?:me )?twice|double[- ]charged|charged (?:me )?(?:two|2) times"
            r"|unauthori[sz]ed (?:charge|payment|transaction)"
        ),
    ),
    Rule(
        "content_not_on_spotify",
        "content_availability",
        _r(
            r"(?:isn'?t|is not|not|no longer|aren'?t) on spotify"
            r"|put .{1,40} (?:back )?on spotify"
            r"|when (?:will|is) .{1,40} (?:be |coming )?(?:on|to) spotify|#reputation"
        ),
    ),
]

PREFILTER_RULE = "prefilter_short"


def word_count(text: str) -> int:
    """Words left after removing placeholders; tokens without letters/digits don't count."""
    cleaned = text.replace("<URL>", " ").replace("@user", " ")
    return sum(1 for tok in cleaned.split() if any(ch.isalnum() for ch in tok))


def apply_rules(text: str) -> tuple[str, str, bool] | None:
    """Return (intent, rule_name, overrides_reused) or None.

    The <=2-word pre-filter wins outright. Otherwise, if several rules fire, the
    intent highest in INTENT_PRIORITY wins (same mechanics as tie-break rule 3).
    """
    if word_count(text) <= MAX_WORDS_INSUFFICIENT:
        return "insufficient_context", PREFILTER_RULE, True
    hits = [r for r in RULES if r.pattern.search(text)]
    if not hits:
        return None
    best = min(hits, key=lambda r: INTENT_PRIORITY.index(r.intent))
    return best.intent, best.name, best.overrides_reused


# --------------------------------------------------------------------------- prompt

#: One or two TRAIN tickets per label. All are in the train split and none is a
#: (demoted) golden row; checked at runtime by check_few_shot().
FEW_SHOT: list[tuple[str, str]] = [
    ("36734", "playback_error"),
    ("228277", "app_platform_bug"),
    ("1844102", "app_platform_bug"),
    ("715300", "account_access"),
    ("944974", "account_compromise"),
    ("1785736", "billing_charge_dispute"),
    ("274129", "billing_charge_dispute"),
    ("963744", "premium_activation_failure"),
    ("1035812", "student_discount_billing"),
    ("1883269", "family_plan_management"),
    ("407161", "cancellation_request"),
    ("370271", "content_availability"),
    ("1786486", "content_availability"),
    ("737841", "content_availability"),
    ("38955", "playlist_issue"),
    ("2308807", "playlist_issue"),
    ("211139", "feature_complaint"),
    ("936220", "artist_creator"),
    ("265069", "venting_no_request"),
    ("1275672", "insufficient_context"),
    ("61161", "insufficient_context"),
    ("19785", "insufficient_context"),
    ("211122", "other"),
]

LABEL_GUIDE = """\
playback_error: audio fails to play, stutters, skips, wrong track plays
app_platform_bug: app/web player/website crashes or misbehaves, outage, downloads vanish, or Spotify on a device (Alexa/Echo, Sonos, Roku, TV, car, receiver, console) not working
account_access: can't log in, forgot password, logged out, Facebook login, email/username lookup
account_compromise: someone else is using or changed the account, hacked, stolen (any phrasing)
billing_charge_dispute: wrong amount, charged twice, charged after cancelling, unknown charges, refund, payment or card problems
premium_activation_failure: paid, but Premium not active or account shows free
student_discount_billing: student discount, verification, UNiDAYS/NUS, Student + Hulu
family_plan_management: adding/removing Family members, invites, switching to/from Family
cancellation_request: wants to cancel or unsubscribe, or asks how cancelling works
content_availability: a listener wants a song/album/artist/podcast that is missing, removed, greyed out, "please add/upload X", a petition to get music on Spotify, wrong song or album info on an artist page, or Spotify not available in their country ("when are you coming to Israel")
playlist_issue: playlist or saved library lost or changed, shuffle or Daily Mix repeating the same songs, bad recommendations; Spotify-made playlists (Wrapped, Top Songs 2017, Year in Music, Discover Weekly) missing or late
feature_complaint: asks for functionality that doesn't exist (lyrics, iPhone X support, Apple Watch, sleep timer, changing username, exporting playlists, more download room)
artist_creator: an artist/label about their OWN music: verification, artist page, Spotify for Artists, uploads, distributor, pitching their music for a playlist, listing their gigs
venting_no_request: praise, thanks or a complaint with no actionable ask
insufficient_context: no identifiable problem: generic "help me", "how do I contact someone", "question about billing", "check your DM", "did you get my email", or emotion/an image with no subject
other: RARE (under 5%). Only a concrete, described request about none of the topics above: concert presale codes, jobs, sponsorship, partner offers"""

SYSTEM_PROMPT = f"""You label customer tweets sent to @SpotifyCares with exactly one intent.

Intents:
{LABEL_GUIDE}

Rules:
1. Several issues: pick the one the customer asks to be fixed.
2. Still tied: pick the one that comes first in the list above.
3. A listener asking where a song went is content_availability; an artist asking about their own music is artist_creator.
4. If anything readable is there (even praise), it is not insufficient_context.
5. Profanity or anger alone does not change the intent.
6. Before answering other, check every intent above again; a missing song, a device problem or a charge is never other.
7. Wanting contact or help without saying what the problem is: insufficient_context. If a concrete problem is named, label the problem.
8. An angry, sarcastic or rude tweet that names a concrete problem ("app not playing", "can't download", "site down", "so quiet") is labelled by that problem. venting_no_request is only for praise, thanks, or a complaint with no concrete problem.

Reply with JSON only: {{"intent": "<one intent name>"}}"""



def build_messages(text: str, examples: list[tuple[str, str]]) -> list[dict]:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for ex_text, intent in examples:
        msgs.append({"role": "user", "content": ex_text})
        msgs.append({"role": "assistant", "content": json.dumps({"intent": intent})})
    msgs.append({"role": "user", "content": text})
    return msgs


def parse_reply(content: str) -> str | None:
    """Validate the model's JSON. None means a parse failure (bad JSON or unknown label)."""
    try:
        intent = json.loads(content)["intent"]
    except (ValueError, KeyError, TypeError):
        return None
    return intent if intent in INTENTS else None


def label_confidence(content: str, logprobs: list[dict]) -> float | None:
    """Probability the model gave the label it wrote: exp(sum of logprobs of its tokens).

    Uses the tokens overlapping the intent value in the JSON. Self-reported confidence
    was useless in the pilot (the model copied 0.9 from the few-shot examples).
    """
    m = re.search(r'"intent"\s*:\s*"([^"]*)"', content)
    if not m or not logprobs:
        return None
    start, end = m.span(1)
    pos, total, used = 0, 0.0, 0
    for tok in logprobs:
        t_start, pos = pos, pos + len(tok["token"])
        if t_start < end and pos > start:
            total += tok["logprob"]
            used += 1
    if pos != len(content) or used == 0:  # tokens don't line up with the text
        return None
    return round(math.exp(total), 4)


# --------------------------------------------------------------------------- LLM client


class OllamaClient:
    def __init__(self, host: str, model: str, timeout: float = 120.0):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """Return (content, token logprobs). format=json constrains structure only, so
        the label tokens are sampled freely and their logprobs are real."""
        body = {
            "model": self.model,
            "messages": messages,
            "format": "json",
            "logprobs": True,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0, "seed": 0, "num_ctx": 4096},
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read())
        return data["message"]["content"], data.get("logprobs") or []


def make_client() -> OllamaClient:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    provider = os.getenv("LLM_PROVIDER", "ollama")
    if provider != "ollama":
        raise NotImplementedError(f"LLM_PROVIDER={provider!r} not wired yet; use ollama")
    return OllamaClient(
        os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
    )


# --------------------------------------------------------------------------- cache


def load_cache(path: Path = CACHE) -> dict[tuple[str, str, str], dict]:
    out: dict[tuple[str, str, str], dict] = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    out[(r["ticket_id"], r["model"], r["prompt_version"])] = r
    return out


def append_cache(rec: dict, path: Path = CACHE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def label_with_llm(
    tickets: pd.DataFrame, client, examples, cache: dict, cache_path: Path = CACHE
) -> list[dict]:
    """Label tickets (ticket_id, ticket_text), using/filling the cache. Returns records."""
    out = []
    for i, (tid, text) in enumerate(zip(tickets["ticket_id"], tickets["ticket_text"], strict=True)):
        key = (tid, client.model, PROMPT_VERSION)
        if key in cache:
            out.append(cache[key])
            continue
        t0 = time.perf_counter()
        try:
            content, logprobs = client.chat(build_messages(text, examples))
            err = None
        except Exception as e:  # network/timeout: record, don't crash a long run
            content, logprobs, err = "", [], f"{type(e).__name__}: {e}"
        dt = time.perf_counter() - t0
        parsed = parse_reply(content) if err is None else None
        rec = {
            "ticket_id": tid,
            "model": client.model,
            "prompt_version": PROMPT_VERSION,
            "intent": parsed,
            "confidence": label_confidence(content, logprobs) if parsed else None,
            "raw": content[:300],
            "error": err or (None if parsed else "parse_failure"),
            "latency_s": round(dt, 3),
        }
        if parsed:  # failures are not cached, so a rerun retries them
            append_cache(rec, cache_path)
            cache[key] = rec
        out.append(rec)
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(tickets)}  last {dt:.2f}s", flush=True)
    return out


# --------------------------------------------------------------------------- inputs


def load_inputs():
    from data.september import (
        V2_REVERIFY,
        WEAK_RAW,
        dedupe_weak,
        read_golden_draft,
        read_jsonl,
    )

    train = pd.read_parquet(PROCESSED / "train.parquet")[["ticket_id", "ticket_text"]]
    weak = dedupe_weak(read_jsonl(WEAK_RAW))
    weak = weak[(weak["confidence"] >= 0.6) & (weak["intent"] != "other")]
    weak = weak[weak["case_id"].isin(train["ticket_id"])]

    gold = read_golden_draft()
    gold = gold[gold["case_id"].isin(train["ticket_id"])]
    golden_ids = set(gold["case_id"])
    human = gold[~gold["case_id"].isin(V2_REVERIFY)]
    return train, weak, human, golden_ids


def check_few_shot(train: pd.DataFrame, golden_ids: set[str]) -> list[tuple[str, str]]:
    text = dict(zip(train["ticket_id"], train["ticket_text"], strict=True))
    for tid, intent in FEW_SHOT:
        assert tid in text, f"few-shot {tid} is not a train ticket"
        assert tid not in golden_ids, f"few-shot {tid} is a (demoted) golden row"
        assert intent in INTENTS
    return [(text[tid], intent) for tid, intent in FEW_SHOT]


def plan_sources(train, weak, human) -> pd.DataFrame:
    """Decide the non-LLM label for every train ticket; the rest is the LLM pool."""
    reused = dict(zip(weak["case_id"], zip(weak["intent"], weak["confidence"], strict=True), strict=True))
    human_lab = dict(zip(human["case_id"], human["intent"], strict=True))
    rows = []
    for tid, text in zip(train["ticket_id"], train["ticket_text"], strict=True):
        rule = apply_rules(text)
        if tid in human_lab:
            rows.append((tid, human_lab[tid], 1.0, "human", None))
        elif tid in reused and rule and rule[2] and rule[0] != reused[tid][0]:
            rows.append((tid, rule[0], RULE_CONFIDENCE, "rule_override", rule[1]))
        elif tid in reused:
            rows.append((tid, reused[tid][0], reused[tid][1], "reused", None))
        elif rule:
            rows.append((tid, rule[0], RULE_CONFIDENCE, "rule", rule[1]))
        else:
            rows.append((tid, None, None, "llm", None))
    return pd.DataFrame(rows, columns=["ticket_id", "silver_intent", "confidence", "source", "rule"])


# --------------------------------------------------------------------------- commands


def _summary(recs: list[dict], title: str) -> None:
    new = [r for r in recs if r.get("latency_s") is not None]
    fails = sum(1 for r in recs if r["intent"] is None)
    lat = pd.Series([r["latency_s"] for r in new]) if new else pd.Series(dtype=float)
    print(f"\n== {title}: {len(recs)} tickets, parse failures {fails}")
    if len(lat):
        print(f"   s/call mean {lat.mean():.2f}  p50 {lat.median():.2f}  p95 {lat.quantile(0.95):.2f}"
              f"  (first call {lat.iloc[0]:.2f}, includes model load)")
    dist = Counter(r["intent"] for r in recs if r["intent"])
    for intent in INTENT_PRIORITY:
        if dist[intent]:
            print(f"   {intent:<28}{dist[intent]:>5}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="silver labels for the train split")
    ap.add_argument("--pilot", type=int)
    ap.add_argument("--check-reused", type=int)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--assemble", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED, help="pilot sample seed")
    args = ap.parse_args(argv)

    train, weak, human, golden_ids = load_inputs()
    examples = check_few_shot(train, golden_ids)
    plan = plan_sources(train, weak, human)
    few_ids = {tid for tid, _ in FEW_SHOT}
    print("source plan:", plan["source"].value_counts().to_dict())
    print("rules fired:", plan["rule"].value_counts().to_dict())

    pool = train.merge(plan[plan["source"] == "llm"][["ticket_id"]], on="ticket_id")
    pool = pool[~pool["ticket_id"].isin(few_ids)]

    if args.pilot or args.check_reused or args.run:
        client = make_client()
        cache = load_cache()
        print(f"model {client.model}, prompt {PROMPT_VERSION}, cached {len(cache)}")

    if args.pilot:
        sample = pool.sample(args.pilot, random_state=args.seed)
        recs = label_with_llm(sample, client, examples, cache)
        _summary(recs, f"pilot ({client.model})")
        key_path = Path("data/interim/pilot_reference_key.json")
        if key_path.exists():  # hand-checked labels (my judgement, not gold)
            key = json.loads(key_path.read_text())
            scored = [(r["intent"], key[r["ticket_id"]]) for r in recs if r["ticket_id"] in key]
            if scored:
                acc = sum(a == b for a, b in scored) / len(scored)
                print(f"   vs hand-check key: {acc:.0%} of {len(scored)}")

    if args.check_reused:
        reused = plan[plan["source"] == "reused"]
        reused = reused[~reused["ticket_id"].isin(few_ids)].sample(args.check_reused, random_state=SEED)
        sample = train.merge(reused[["ticket_id", "silver_intent"]], on="ticket_id")
        recs = label_with_llm(sample, client, examples, cache)
        _summary(recs, "reused check")
        new = dict((r["ticket_id"], r["intent"]) for r in recs)
        sample["new"] = sample["ticket_id"].map(new)
        sample["agree"] = sample["new"] == sample["silver_intent"]
        print(f"\n   overall agreement {sample['agree'].mean():.2%} ({sample['agree'].sum()}/{len(sample)})")
        per = sample.groupby("silver_intent").agg(n=("agree", "size"), agree=("agree", "mean"))
        per["top_new_label_when_disagree"] = sample[~sample["agree"]].groupby("silver_intent")["new"].agg(
            lambda s: s.value_counts().head(2).to_dict()
        )
        print(per.sort_values("agree").to_string())
        sample.to_csv("data/interim/reused_check.csv", index=False)

    if args.run:
        todo = pool.head(args.limit) if args.limit else pool
        _summary(label_with_llm(todo, client, examples, cache), "run")

    if args.assemble:
        cache = load_cache()
        model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        llm = {k[0]: v for k, v in cache.items() if k[1] == model and k[2] == PROMPT_VERSION}
        out = plan.copy()
        out["model"] = None
        out["prompt_version"] = None
        out.loc[out["source"] == "reused", "model"] = "qwen3:14b"
        out.loc[out["source"] == "reused", "prompt_version"] = "september"
        is_llm = out["source"] == "llm"
        out.loc[is_llm, "silver_intent"] = out.loc[is_llm, "ticket_id"].map(
            lambda t: llm.get(t, {}).get("intent"))
        out.loc[is_llm, "confidence"] = out.loc[is_llm, "ticket_id"].map(
            lambda t: llm.get(t, {}).get("confidence"))
        out.loc[is_llm, "model"] = model
        out.loc[is_llm, "prompt_version"] = PROMPT_VERSION
        out["rule"] = out["rule"].where(out["source"].isin(["rule", "rule_override"]))
        out = out.dropna(subset=["silver_intent"])
        out.to_parquet(OUT, index=False)
        print(f"wrote {OUT}: {len(out)} rows", out["source"].value_counts().to_dict())


if __name__ == "__main__":
    main()
