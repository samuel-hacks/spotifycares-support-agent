# Decision log

Dated entries for the choices that shape the project. Newest at the bottom.

**Current milestone: Day 2: silver labels done; golden set pending (339-row sheet not yet labelled).** Day 2 counts as done only when `eval/golden.jsonl` exists with 300+ labelled items.

---

## 2026-11-27: Brand is SpotifyCares

Fixed from the original take-home (spec 1.1). SpotifyCares has 43,265 replies in twcs.csv, which is plenty for retrieval, and its tickets cover a wide spread of topics (billing, devices, catalogue, app bugs), so the intent problem is not trivial.

## 2026-11-27: Repo root and Python version

The spec layout calls the root `support-agent/`. I'm using the existing project folder as the root and keeping everything else in the spec layout. The spec moved to `docs/PROBLEM_STATEMENT.md`.

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

The hand-check key (99 tickets) is Claude-labelled, prompt tuned on it, optimistic. It is not gold and is not the headline quality number; that is the comparison with the 80 human labels (see "Silver labels, final numbers").

**Independent check: v4 vs the reused qwen3:14b labels**, seeded random 200: 73% agreement overall. The lowest intents were `premium_activation_failure` 42%, `playback_error` 55% and `playlist_issue` 60% (n=5). Reading all 54 disagreements, the old label was right in most of them: llama spreads Premium problems ("still getting adverts although I pay for premium") over app, access and playback, and calls feature requests venting. Only 2 of the 200 moved to `insufficient_context`, so the old labels are barely stale under v2. Decision at the time: reuse all intents. Low agreement comes from the new model, not from stale old labels. This was later replaced by an agreement filter for the low intents (see "Reuse agreement filter").

**Confidence is informative.** On the hand-check key (Claude-labelled, prompt tuned on it, optimistic), LLM labels with confidence of 0.8 or more were 92% correct and kept 73% of tickets. At 0.9 they were 95% correct, keeping 59%. Against qwen3:14b, agreement rises from 73% (all) to 87% at 0.9 or more.

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

## 2026-11-27: Silver labels, final numbers

**Headline quality number: silver vs the 80 human labels.** I ran the same model and prompt on the 80 train tickets that have a human label (they keep the human label in the silver set; these LLM labels went to a separate cache). It agreed on 71% of them (57/80), on 89% of the 53 at confidence 0.8 or above, and on 91% of the 43 at 0.9 or above. The prompt was never tuned on these rows. The weak spot is app_platform_bug: 4 of 13 right, with misses spread over playlist_issue, playback_error and others. The 80 rows are September golden rows I labelled, so they share my biases; the golden set is the real test.

The full LLM run labelled 17,466 train tickets with llama3.1:8b (Q4_K_M) through Ollama, prompt silver-v4, temperature 0. There were 0 parse failures and 0 request errors. Median time per call was 0.96 s (mean 1.05 s). It took about 5 hours, because macOS Photos analysis and a VM slowed it to about 3 s per call for a stretch in the middle.

Pilot (50 tickets, v4 prompt): about 0.52 s per call, 0 parse failures, `other` on 3 to 4 of 50. On the 99-ticket hand-check key (Claude-labelled, prompt tuned on it, optimistic) it scored 76% to 80%. The first v1 pilot put 15 of 50 in `other`, which is why the prompt went through v2 to v4.

Reuse check (200 reused September labels, seed 13, LLM vs old qwen3:14b label): 73% overall. Per intent: premium_activation_failure 0.42 (n=19), playback_error 0.55 (11), playlist_issue 0.60 (5), app_platform_bug 0.67 (15), account_access 0.69 (13), feature_complaint 0.71 (42), venting_no_request 0.71 (7), billing_charge_dispute 0.75 (20), student_discount_billing 0.81 (16), account_compromise 0.82 (11), family_plan_management 0.86 (14), content_availability 0.95 (21), cancellation_request 1.00 (6).

## 2026-11-27: Reuse agreement filter (disagreement means drop)

For the seven intents whose reuse agreement was below 0.75 (premium_activation_failure, playback_error, playlist_issue, app_platform_bug, account_access, feature_complaint, venting_no_request), a reused label is kept only if the new LLM label agrees. If they disagree, the ticket is **dropped from training**: its source becomes `dropped_disagreement`, and it stays in `silver_labels.csv` with the reused label so it can be audited. Reused labels for intents at 0.75 or above are kept as they are. This is Vijay's call and replaces my earlier "reuse everything" decision. The intent list is `REUSE_CHECK_LOW` and the training rule is `select_for_training` in `data/label_silver.py`. The two few-shot tickets in this group keep their reused label.

A first version replaced the reused label with the LLM label instead. That was rejected because it copies the new model's biases into training, and premium_activation_failure shows the bias clearly:

- In the 200-row reuse check the LLM agreed on only 8 of the 19 old premium labels, and it never said premium where the old label didn't (8 premium predictions in all). It under-predicts premium; it doesn't over-predict it.
- Fresh LLM labels are 2.9% premium (503 of 17,466; 273 at 0.8 or above), against 6.6% of the reused labels (148 of 2,254). The reused set is not a random sample (September kept only non-`other` labels at 0.6 or above), so this gap is a hint, not a measurement. It still suggests premium is undercounted in the LLM part of silver, which is 84% of it. The golden set will tell.
- Of the 476 replacements, only 1 became premium. That figure is partly by construction (an old premium label that disagrees can't be replaced with premium), so the two points above are the real evidence.

1,320 reused tickets in these intents were LLM-labelled (0 parse failures); 476 disagreed and were dropped:

| reused intent | reused | kept | dropped |
|---|---:|---:|---:|
| feature_complaint | 468 | 317 | 151 |
| account_access | 200 | 134 | 66 |
| app_platform_bug | 186 | 134 | 52 |
| premium_activation_failure | 148 | 62 | 86 |
| playback_error | 137 | 61 | 76 |
| venting_no_request | 99 | 79 | 20 |
| playlist_issue | 84 | 59 | 25 |

Fresh LLM labels vs reused labels (share of each source):

| intent | fresh LLM | % | reused | % |
|---|---:|---:|---:|---:|
| feature_complaint | 3,168 | 18.1 | 468 | 20.8 |
| content_availability | 3,004 | 17.2 | 246 | 10.9 |
| account_access | 1,086 | 6.2 | 200 | 8.9 |
| billing_charge_dispute | 705 | 4.0 | 196 | 8.7 |
| app_platform_bug | 1,540 | 8.8 | 186 | 8.3 |
| family_plan_management | 732 | 4.2 | 163 | 7.2 |
| student_discount_billing | 572 | 3.3 | 156 | 6.9 |
| premium_activation_failure | 503 | 2.9 | 148 | 6.6 |
| playback_error | 664 | 3.8 | 137 | 6.1 |
| account_compromise | 302 | 1.7 | 113 | 5.0 |
| venting_no_request | 1,403 | 8.0 | 99 | 4.4 |
| playlist_issue | 1,107 | 6.3 | 84 | 3.7 |
| cancellation_request | 153 | 0.9 | 58 | 2.6 |
| artist_creator | 147 | 0.8 | 0 | 0.0 |
| insufficient_context | 676 | 3.9 | 0 | 0.0 |
| other | 1,704 | 9.8 | 0 | 0.0 |

The billing, family, student, compromise and cancellation classes are also smaller in the fresh LLM labels; some of that is the rules taking those tickets first (account_compromise_hacked, billing_double_charge).

`data/labels/silver_labels.csv` (committed) and `data/processed/silver_train.parquet` (gitignored, has tweet text) have 20,701 rows by source:

| source | rows |
|---|---:|
| llm | 17,466 |
| reused | 1,778 |
| rule | 900 |
| dropped_disagreement | 476 |
| human | 80 |
| rule_override | 1 |

The 16 tickets used as few-shot examples are left out (train has 20,717). Rules fired: content_not_on_spotify 290, account_compromise_hacked 227, prefilter_short 204, billing_double_charge 86, artist_creator_own_profile 64, artist_creator_s4a 13, playlist_wrapped 10, artist_creator_distribution 7.

LLM confidence is exp(sum of label-token logprobs). The cut-off is a training-time parameter (`select_for_training`, default 0.8), not baked into the labels. Training uses every human, rule, rule_override and kept reused label, never a dropped one, plus LLM labels at the cut-off or above: 14,167 tickets at 0.8 and 17,198 at 0.6.

| intent | silver (not dropped) | dropped | train at 0.6 | train at 0.8 |
|---|---:|---:|---:|---:|
| content_availability | 3,548 | 0 | 3,268 | 2,878 |
| feature_complaint | 3,501 | 151 | 3,075 | 2,625 |
| app_platform_bug | 1,687 | 52 | 1,394 | 1,126 |
| venting_no_request | 1,486 | 20 | 1,214 | 927 |
| account_access | 1,225 | 66 | 996 | 804 |
| playlist_issue | 1,178 | 25 | 994 | 776 |
| family_plan_management | 899 | 0 | 848 | 771 |
| other | 1,706 | 0 | 1,209 | 768 |
| insufficient_context | 880 | 0 | 794 | 703 |
| billing_charge_dispute | 993 | 0 | 762 | 608 |
| student_discount_billing | 738 | 0 | 667 | 568 |
| account_compromise | 649 | 0 | 598 | 565 |
| playback_error | 726 | 76 | 548 | 396 |
| premium_activation_failure | 567 | 86 | 443 | 337 |
| artist_creator | 231 | 0 | 200 | 168 |
| cancellation_request | 211 | 0 | 188 | 147 |

`silver_labels.csv` holds only ticket_id, silver_intent, confidence, source, model and prompt_version, so it carries no Kaggle tweet text. `make silver RAW=path/to/twcs.csv` rebuilds the splits from twcs.csv and then `silver_train.parquet` (labels joined to train text) from the CSV; a test checks that the rebuild matches the parquet exactly. The LLM caches and run logs stay gitignored in `data/interim`.

## 2026-11-27: Planned Day 3 experiment, confidence cut-off

Compare training with LLM labels at 0.6 and at 0.8 or above, scored on val per-class F1 (never on the golden set). 0.8 is more precise (89% vs 71% agreement with the human labels overall); 0.6 keeps 3,031 more tickets. Watch billing_charge_dispute in particular: only 45% of its LLM labels survive 0.8 (67% survive 0.6), and it is an always-escalate intent, so recall on it matters more than for most classes. playback_error and premium_activation_failure are the other classes that shrink most at 0.8, and premium is probably undercounted already (see the reuse filter entry). Pick the cut-off per the val result and record it here.

## 2026-11-27: CLAUDE.md is local only

CLAUDE.md is no longer tracked; it and `.claude/` stay on disk and are gitignored. The no-attribution setting lives in the local `.claude/settings.json`.
