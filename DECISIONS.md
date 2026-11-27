# Decision log

Dated entries for the choices that shape the project. Newest at the bottom.

**Current milestone: Day 2 nearly done. Taxonomy v2, silver labelling (full LLM run in progress), golden sample and labelling guide ready; golden labelling by Vijay next.**

---

## 2026-11-27: Brand is SpotifyCares

Fixed from the original take-home (spec 1.1). SpotifyCares has 43,265 replies in twcs.csv, which is plenty for retrieval, and its tickets cover a wide spread of topics (billing, devices, catalogue, app bugs), so the intent problem is not trivial.

## 2026-11-27: Repo root and Python version

The spec layout calls the root `support-agent/`. I'm using the existing project folder as the root and keeping everything else in the spec layout. The spec moved to `docs/PROBLEM_STATEMENT.md`, which is where CLAUDE.md expects it.

Python 3.12 in a uv-managed `.venv`. The system Python is 3.14 and torch/transformers wheels for it are still patchy, so 3.12 is the safe choice for Day 3.

Dependencies are split. `requirements.txt` has only what Day 1 needs; torch, transformers and sentence-transformers go into `requirements-ml.txt` on Day 3. CI then installs in seconds instead of pulling a 700 MB torch wheel just to test data prep.

## 2026-11-27: How a ticket/reply pair is built

Options considered:
1. Every (customer tweet, SpotifyCares reply) pair. This gives 41k pairs, but many "tickets" are follow-ups like "iPhone 8" or a bare version number that mean nothing on their own.
2. The first customer tweet of each conversation plus the first SpotifyCares reply to it directly.

I went with option 2 (spec 3.2 step 3). The root of each thread is found by walking `in_response_to_tweet_id` upward. The full thread is kept as JSON in a `thread` column in case context helps later. Funnel: 28,280 conversations, 26,094 with a direct reply to a customer root, and 25,897 left after dropping 133 empty and 64 duplicate tickets. Full numbers are in `data/DATA_CARD.md`.

## 2026-11-27: Brand mentions and signatures

`@115888` never writes a reply but is mentioned 14,212 times in tickets sent to SpotifyCares (against 25,973 for `@SpotifyCares` itself). It's the anonymised main @Spotify account, so it gets stripped like the brand handle. All other handles become `@user`.

Agent signatures look like `/NJ` at the end of a reply, not `^JD` as the spec guessed. I handle both. 97.3% of replies had one (204 different agents). The signature is kept in `reply_signature`. The DM-button link after the signature is removed and flagged in `reply_has_dm_link` (28.9% of replies), since "move to DM" is a routing signal. Some replies also start with a `1:` part marker, which is removed.

Real URLs stay in `reply_text`. The drafter's post-check needs to know which links really appeared in past replies, and `<URL>` would hide that. `reply_clean` has the masked version for models.

## 2026-11-27: Time-based split

Oldest 80% train, next 10% val, newest 10% test, by ticket time. Train ends 2017-11-22, val runs 2017-11-22 to 11-28, test 2017-11-28 to 12-03. SpotifyCares reuses near-identical replies and customers tweet the same complaint many times during an outage or an album release (Taylor Swift's Reputation shows up constantly), so a random split would leak near-duplicates across splits and inflate every score. A time split also matches how the agent would really be used: trained on the past, run on new tickets.

## 2026-11-27: Non-English tickets are kept

95.3% of tickets are English by langdetect. The rest is a long tail (Indonesian 0.9%, French and German 0.4% each). They stay in the data with a `lang` column. Dropping 5% isn't worth it when SpotifyCares answered them in English anyway, and per-language results can go in the report.

## 2026-11-27: Intent taxonomy, first draft (superseded by Taxonomy v2 below)

I ran keyword probes over the train tickets and read a few hundred unmatched ones. The spec's starting list mostly holds, with two changes:

- `podcasts_content` is renamed to **`content_availability`**. Most of these tickets are about music, not podcasts: "why isn't Reputation on Spotify", "put Lil Peep back", "launch in India". Podcasts are about 0.6% of tickets.
- **`artist_creator`** is new. Artists asking about verification, getting their music on Spotify, or their track being under the wrong artist are about 4% of tickets, and SpotifyCares answers them differently (it points them to Spotify for Artists or their distributor). Leaving them in content_availability would mix two kinds of replies.

Final list (11 intents):

| intent | covers | edge cases |
|---|---|---|
| account_login | can't log in, password reset, hacked or stolen account, email/username change, Facebook login | "hacked/locked" always escalates |
| billing_payment | double charges, refunds, failed payment, card update, price questions | always escalates |
| subscription_plan | Premium, Family, Student, Duo, trials, upgrade, downgrade, cancel, ads on the free tier | complaints about ads go here: the answer is about the free tier |
| playback_app_bug | crashes, skipping, no sound, app or web player not loading, outages, bad updates | "app is down for everyone" goes here |
| device_connect | Spotify Connect, Alexa/Echo, Sonos, Chromecast, car, TV, consoles, watches, Bluetooth | a bug that only happens on one device goes here, not playback_app_bug |
| offline_downloads | downloads missing, offline mode, storage, data use from downloads | |
| library_playlists | lost playlists, liked songs, library, Discover Weekly and other recommendations, following | |
| content_availability | missing or greyed-out songs/albums/podcasts, region launch, lyrics, wrong metadata reported by a listener | the artist asking about their own track goes to artist_creator |
| artist_creator | artist verification, uploading music, Spotify for Artists, royalties, own release under the wrong artist | |
| feature_request | "please add X", "you should let us...", ideas | "why can't I X" is a feature request only if X doesn't exist; otherwise it's a bug |
| praise_other | thanks, compliments, chit-chat, presale codes and concerts, vague "DM me" with no topic, spam, unrelated | catch-all; keeps the other classes clean |

Rough keyword coverage before any LLM labelling: 76% of train tickets hit at least one rule, and 35% hit more than one. That's why keywords alone won't do for silver labels; the LLM pass on Day 2 settles the overlaps. If the golden set shows a class is too small to learn (artist_creator is the most likely one), I'll come back here before merging it.

## 2026-11-27: Demo stack (fixed, not Streamlit)

Flask REST API with an app factory and blueprints, plus a separate plain HTML/CSS/JS frontend. This was fixed in the original brief. Streamlit would be faster to put together, but it ties the UI to Python, hides the API, and doesn't show you can build a proper backend. A JSON API also lets the eval harness hit the same `/api/triage` endpoint the demo uses, so the latency numbers are real.

## 2026-11-27: September work reused as provenance

My September version of this project has a locked taxonomy, a labelling guide, 200 hand-labelled golden items and qwen3:14b weak labels. They're copied into `reference/september/`. `taxonomy_locked.md` and `labeling_guide.md` are committed so the history of the taxonomy is visible. The CSV and JSONL files there stay local (gitignored): golden labels will live in `eval/golden.jsonl`, and the weak labels only matter as an input to silver labelling.

September `case_id` is the twcs `tweet_id` of the customer tweet. All 200 golden texts match the raw CSV exactly, and all 200 link to a `ticket_id` in the new splits.

## 2026-11-27: Taxonomy v2 (16 labels), replacing the 11-intent draft

I compared my Day 1 draft (11 topic buckets) with the September taxonomy (14 labels). The September one splits along who resolves the ticket: account compromise vs plain login trouble, a wrong charge (finance) vs Premium not activating (technical), student vs family vs cancellation. My draft grouped by topic and lost those splits. The September labels also came with an agreement-tested priority order, 200 golden labels and about 2.4k weak labels, all in that scheme. So v2 starts from the 14 and changes five things:

1. `artist_creator` is added (priority rank 13, between `feature_complaint` and `venting_no_request`: creator support has no money or security at stake). It's about 1.2 to 1.4% of tickets in every split and SpotifyCares answers it with its own reply family (Spotify for Artists, the distributor).
2. `content_availability` also covers region launch and availability ("launch in India"). As its own class it would be about 0.5% of tickets, roughly 13 in test, too few to learn or evaluate, and the reply is the same "not available there yet" family.
3. `playlist_issue` also covers Spotify-made playlists: Wrapped / Your Top Songs, Discover Weekly, Daily Mix, Release Radar.
4. `insufficient_context` is both a hard rule pre-filter (2 words or fewer after removing `@user` and `<URL>`) and a learned label, for the cases a rule can't catch: generic help requests, "did you get my DM?", or emotion/an image with no subject. Both lead to the clarifying-question action.
5. `other` now means an identifiable issue that fits nothing, and its default action is escalate (there's no reply family to ground a draft on).

Why: in the September golden draft, `other` was 25/200 = 12.5%, over the 5% cap. Reading all 25: 9 had no identifiable issue, 4 were region launch, 4 were Wrapped / Top Songs 2017, 3 were artist or creator questions, and 5 were truly other. Adding artist_creator and a region class alone would still leave `other` at 9%. With all five changes it's about 2 to 2.5%.

**Going past the spec's "8 to 12".** v2 has 16 labels: 13 substantive intents plus `venting_no_request`, `insufficient_context` and `other`. The extra classes come from routing ownership. Merging back to 12 would put finance tickets in the same class as technical ones and hacked accounts in the same class as forgotten passwords, and those pairs route differently (escalate vs auto-handle). A wrong merge there costs routing precision on exactly the tickets that matter most. Three extra classes cost the classifier a little; I'll watch the small ones (cancellation_request, playlist_issue, artist_creator) in the per-class F1 and merge if one turns out unlearnable.

**Priority order.** `insufficient_context` sits at rank 15, below `venting_no_request` and above `other`. It's defined by the absence of a readable issue, so if anything can be read (even praise) the context isn't insufficient, and every real intent should win a tie. It ranks above `other` because `other` claims there is an issue that no label fits. When an annotator can't decide between "nothing visible" and "something I can't place", a clarifying question gets more information, and `other` has no resolution path.

The taxonomy lives in `agent/taxonomy.py` (ported from September's `src/data/taxonomy.py`, version `v2-2026-11-27`). One part of the September module was left out on purpose: its `CONFIDENCE_THRESHOLD = 0.75` and `CLARIFY_MARGIN = 0.10` were tuned on the golden set. Here the golden set is never used for tuning, so thresholds get tuned on val on Day 4.

## 2026-11-27: Known limitation, Wrapped seasonal shift

Wrapped / "Your Top Songs 2017" tickets are 0.08% of train, 0.27% of val and 1.24% of test. Wrapped launched in early December 2017, which is exactly the test window, so the classifier sees almost none of them in training. No special handling in training: this is the kind of drift a time split is meant to expose, and it goes in REPORT.md as a known limitation with the per-class result.

## 2026-11-27: September weak labels, dedupe check

`weak_labels.jsonl` has 4,812 lines for 2,500 cases (2,312 cases were labelled twice, from a resumed run). Deduping by case_id and keeping the last entry gives 2,418 labels at confidence of 0.6 or more, which matches `weak_train.jsonl` + `weak_val.jsonl` exactly (2,418, identical labels and confidences). The September log's final summary says 2,417 because it kept the first entry instead. The two differ on one case, 1990922, labelled `other` at 0.30 the first time and 0.60 the second. The other 10 repeated cases differ only in confidence (by 0.05 to 0.10), never in intent. The 82 dropped cases all had confidence 0.1 to 0.3.

All 2,500 weak-labelled cases fall in the new train split (2 no longer exist as tickets after dedupe), and none overlap the golden draft.

## 2026-11-27: Which September weak labels are reused

I'm using the 2,418 labels on disk (dedupe keeping the last entry), not the 2,417 in the log. Both counts come from the same 2,500 cases; the only difference is case 1990922, which was `other` at 0.30 in the first entry and `other` at 0.60 in the second. Keeping the last entry matches what September actually trained on. In practice it doesn't matter: 1990922 is an old `other` label, and all of those are relabelled anyway (next point).

How the labels are reused in silver labelling:

- The 2,255 non-`other` labels in train become silver labels with `source=reused`. They need no remapping, since the 14 old names are unchanged in v2.
- The 161 old `other` labels go back through the new LLM prompt, because v2 moved most of what used to land there (artist, region, Wrapped, no-issue tickets).
- When a high-precision v2 rule fires on a reused ticket (the 2-word pre-filter, artist_creator, Wrapped), the rule wins and the row is stored with `source=rule_override`.
- The old prompt never saw the v2 definitions, so some non-`other` labels may be stale too, mostly vague tickets that should now be `insufficient_context`. After the pilot I run a seeded random 200 of the reused labels through the new prompt and check agreement per intent. Any intent with low agreement gets relabelled instead of reused.

The reused labels came from qwen3:14b, which is larger than the spec's 3 to 8B. New labels come from a model inside that range. The `source` and `model` columns are kept on every silver row so the two teachers can be compared later.

## 2026-11-27: 139 old golden rows demoted to train/val human labels

Of the 200 September golden items, 61 fall in the new test window and 139 don't (48 val, 91 train), because the September cutoff (2017-11-10) was earlier than this project's time split. The 139 are **demoted**: they never enter `eval/golden.jsonl`, so this is not golden-set leakage. They are used like this:

- The 48 val rows become a `val_human` slice.
- The 91 train rows become human labels that override silver (`source=human`), and silver-vs-human agreement on them gives an early estimate of label noise.
- The 18 of these rows that taxonomy v2 may relabel (7 val, 11 train) are left out of both until I re-verify them (`reference/september/reverify_trainval.csv`).

These rows came from a stratified and adversarial sample, not a random one. So the agreement estimate is biased (hard cases are over-represented), and `val_human` is not a natural distribution. Day 4 threshold tuning uses the full val split as the primary target and `val_human` only as a cross-check.

## 2026-11-27: Self-agreement from the 61 carried-over test rows

The 61 old golden rows in the test window go into the new golden labelling file blind: not pre-filled, mixed in with the new samples, and not marked in my copy. The mapping lives in a separate file I don't open while labelling. Afterwards I compare my September label with my new label on those 61, about 2.5 months apart, and that is my self-agreement number. This replaces the spec's "label 50 twice" pass, which is only brought back if fewer than 50 of the 61 survive into the final set. The golden target stays 300 to 400 test-window tickets in total.

## 2026-11-27: Local LLM for new silver labels

`llama3.1:8b` (Q4_K_M, 4.9 GB) via Ollama, temperature 0, JSON output. It's already installed, it fits the spec's 3 to 8B range, and it runs on the M5 with 16 GB alongside everything else. Provider and model come from `LLM_PROVIDER` / `OLLAMA_MODEL`, so swapping to another model is a config change.

## 2026-11-27: Silver labelling, rules and the LLM pilot

**Keyword rules.** Only high-precision rules are kept. For labels the September teacher knew, I measured each candidate's agreement with the existing labels on train and kept those at 0.90 or above: `account_compromise_hacked` 0.98, `billing_double_charge` 0.95, `content_not_on_spotify` 0.91. Dropped: `family_plan` 0.87, `student_discount` 0.78, `feature_please_add` 0.78, `cancel_request` 0.70, `venting_thanks_only` 0.55. The v2-only rules (`artist_creator_*`, `playlist_wrapped`) couldn't be scored that way, so I read their hits by hand and tightened two: bare "wrapped" matched "Wrapped by George Strait", and "get my music" matched "get my songs on my iPod". The 2-word pre-filter fires on 204 train tickets; a few are short praise ("Thanks spotify!!!!!"), kept as `insufficient_context` because the pre-filter is a hard rule.

**Source plan for the 20,717 train tickets:** 80 human, 1 rule_override, 2,254 reused, 900 rule, 17,482 left for the LLM.

**Prompt iterations** (llama3.1:8b, temperature 0, 0 parse failures in every run):

- v1 (JSON schema, self-reported confidence): 15/50 `other`, mostly missing songs and device problems. Confidence was 0.8 or 0.9 almost every time, copied from the few-shot examples, so it was useless.
- v2: `format: "json"` instead of a schema, and confidence = probability of the label tokens the model wrote (from Ollama's token logprobs). With a schema, Ollama's logprobs come from before the grammar mask, so they can't be used. `other` fell to 10/50, but most of those were generic contact requests.
- v3: added "contact/help without a problem = insufficient_context". Hand-checked against 100 fresh tickets, about 70% correct. The new "venting" rule made it label angry complaints about concrete problems as venting.
- v4: angry tweets that name a problem get that problem's label, plus clearer content/playlist/artist definitions. 76% and 80% on the two hand-checked samples of 50, with `other` at about 7%.

The hand-check key (99 tickets) is my own judgement, not gold, and v4 was tuned on it, so those numbers are optimistic.

**Independent check: v4 vs the reused qwen3:14b labels**, seeded random 200: 73% agreement overall. The lowest intents were `premium_activation_failure` 42%, `playback_error` 55% and `playlist_issue` 60% (n=5). Reading all 54 disagreements, the old label was right in most of them: llama spreads Premium problems ("still getting adverts although I pay for premium") over app, access and playback, and calls feature requests venting. Only 2 of the 200 moved to `insufficient_context`, so the old labels are barely stale under v2. Decision: reuse all intents. Low agreement comes from the new model, not from stale old labels.

**Confidence is informative.** On the hand-check key, LLM labels with confidence of 0.8 or more were 92% correct and kept 73% of tickets. At 0.9 they were 95% correct, keeping 59%. Against qwen3:14b, agreement rises from 73% (all) to 87% at 0.9 or more.

## 2026-11-27: Golden set sampling

`eval/sample_golden.py`, seed 2026, test split only. 339 tickets in three parts:

- 61 **carried**: the September golden rows in the test window, put in blind for the self-agreement check.
- 150 **natural**: a uniform random draw, so true class priors can be reported.
- 128 **stratified**: a top-up until every intent bucket has at least 22 tickets.

The buckets come from a throwaway TF-IDF + LogReg trained on the train labels that already exist (human, reused, rule). It only decides which tickets get sampled; the prediction is never written to the labelling sheet. Nothing is predicted as `other`, because none of those training labels are `other` (reused `other` labels were excluded on purpose), so `other` is only represented through the natural and carried parts. That's fine for a class meant to stay under 5%.

The labelling sheet is shuffled and has no subset, carried flag, silver label or real SpotifyCares reply. The reply is left out because seeing how an agent answered would pull the route label towards it. All of that lives in `data/interim/golden_manifest.csv` and is merged back by `python -m eval.sample_golden build`, which also validates every value before writing `eval/golden.jsonl`. The manifest can be regenerated (fixed seed, and the carried rows come from the September CSV). The "label 50 twice" subset is dropped because all 61 carried rows survived.

`eval/golden.jsonl` is the versioned golden set. (The labelling sheet was first gitignored, then committed; see "Golden labelling sheet is committed".)

## 2026-11-27: Two reason codes added, one spec code narrowed

The September reason codes had no way to say "this needs someone to look at the account", which is the most common reason SpotifyCares moves a ticket to DM. Spec section 6 has `PII` and `NEEDS_ACCOUNT_ACTION` for this, so v2 adds `pii` and `needs_account_action` as gold reason codes, mapped to the spec codes in `SPEC_REASON_CODE`. A public triage question ("which device?") is not `needs_account_action`.

The spec's `ANGRY_OR_RISKY` ("strong negative sentiment, anger, threats to cancel") contradicts the September rule that tone or profanity alone never escalates, which came from real tickets: shouted, sweary bug reports are ordinary bug reports. I kept the September rule. `ANGRY_OR_RISKY` was first narrowed to `bereavement_or_sensitive`; it was then split in two (see "ANGRY_OR_RISKY split" below). `billing_charge_dispute` stays an always-escalate intent, as the spec asks, with `fraud_or_billing_dispute` when unauthorised and `needs_account_action` otherwise. Intent `other` escalates with `out_of_scope`.

## 2026-11-27: Labelling guide

`eval/LABELING_GUIDE.md` is built from the September guide and `taxonomy_locked.md`, updated for v2. It has 44 real examples. A script checked that every one is a train ticket and none is a golden row (demoted or not). It covers the sheet columns, pre-filters, the 16 definitions, 9 tie-break rules, `INTENT_PRIORITY`, routing rules with reason codes (including two false-positive examples: "died a lil" and a joking "sue you"), and the not-built list. One example contains a real phone number, which is redacted in the guide.

## 2026-11-27: What stratified the golden sample (and what it may never be used for)

No LLM or rule labels were put on test tickets. The stratified part of the golden sample used **predictions** from a throwaway TF-IDF + LogReg fitted only on existing **train** labels (80 human, 2,254 reused, 900 rule, 1 rule_override). That model predicted a bucket for each test ticket, and the bucket only decided which tickets were drawn. The predicted buckets are kept in `data/interim/golden_manifest.csv` (`sampling_bucket`, gitignored) so the draw can be audited. They are never shown in the labelling sheet.

These test-split predictions are used for sampling and nothing else: never for training, few-shot examples, calibration or threshold tuning. The same goes for every other label on val or test tickets. Silver labels exist for train only; `tests/test_golden.py` checks that `silver_train.parquet` has no val or test ticket_ids and that the silver inputs are train-only.

## 2026-11-27: Golden labelling sheet is committed

`eval/golden_labeling.csv` is committed so 339 hand labels don't live on one disk. It's safe in the repo because it's blind: its columns are `row, ticket_id, text, text_raw, gold_intent, multi_intent, gold_route, gold_reason, annotator_confidence, notes`, with no subset, carried flag, September label, sampling bucket or reference reply. The rows are shuffled, so carried rows can't be told apart by position either. A test checks the column list. `data/interim/golden_manifest.csv` stays gitignored. This replaces the earlier note saying the sheet was gitignored.

## 2026-11-27: ANGRY_OR_RISKY split into two narrow codes

Spec section 6 escalates on "strong negative sentiment, anger, threats to cancel, or legal words" (ANGRY_OR_RISKY). Escalating on tone conflicts with the September finding that angry, sweary tickets are mostly ordinary bug reports. Legal threats are different, though: they need a human whatever the tone. So ANGRY_OR_RISKY is split into two codes that each need a stated fact, never a tone:

- `bereavement_or_sensitive`: a death, grief or another sensitive disclosure.
- `legal_or_regulatory_threat` (new): explicit legal action or a regulator. That means sue/lawyer/lawsuit/class action, small claims or consumer court, FTC/BBB/ombudsman/trading standards, or a threat to file a chargeback. It is never triggered by profanity, capitals, general anger, threats to cancel, or rhetorical "this is criminal / theft / a crime".

The automatic detector (`agent/taxonomy.py`, `is_legal_or_regulatory_threat`) is a whole-word pattern over those terms. On train it fires on 5 of 20,626 tickets. 2 are real ("Fix this or I'm suing", "Maybe if a lawyer was involved") and 3 are jokes ("imma sue" about an ad, "consider yourself sued", a thank-you that mentions a courthouse). A chargeback only counts as a threat ("file a chargeback"), because one ticket was "I received a chargeback". Over-escalating the odd joke is accepted: the code is rare, and escalating is the safe direction. Gold labels follow what the tweet means, so the labelling guide marks the jokes and the rhetorical "is a crime" as false positives. Tone-only escalation stays out.
