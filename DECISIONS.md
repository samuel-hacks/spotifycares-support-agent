# Decision log

Dated entries for the choices that shape the project. Newest at the bottom.

**Current milestone: Day 1 done (pending CI on GitHub). Next: Day 2, silver labels and golden set.**

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

## 2026-11-27: Intent taxonomy (locked)

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
