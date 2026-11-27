# SpotifyCares Labeling Guide

Annotation reference for the locked intent taxonomy. Source of truth for the label
strings themselves is `src/data/taxonomy.py`; this document is the human-facing
companion that says how to apply them.

**Taxonomy status:** locked. Derived from Stage 2 clustering (k=8/10/12 comparison)
+ 200-case manual open coding + escalation design review. Do not re-derive from
clustering.

Every example below is a **real case drawn from before the leakage cutoff
(2017-11-10)**. None are invented. Post-cutoff cases are deliberately excluded so
that reading this guide cannot contaminate the golden set.

---

## Label space at a glance

- **14 intent labels** — 12 substantive intents plus 2 catch-alls
  (`venting_no_request`, `other`).
- **2 pre-filters** — `insufficient_context`, `non_english`. These are *not*
  intents and run before the classifier.
- **7 escalation reason codes** — an independent axis. A case carries one intent
  *and* zero or more reason codes.
- **3 action branches** — `auto_handle`, `clarify`, `escalate`.

> **Note on the count.** `taxonomy_locked.md` is headed “12 classes” but its
> table defines 14 rows. The 14 split cleanly into 12 substantive intents plus the
> two catch-alls, which is what the “12” appears to count. All 14 are live
> labels: tie-break rule 6 routes unclassifiable cases to `other` and caps it at
> ~5% of the golden set, so `other` is load-bearing.

---

## Pre-classification filters (run BEFORE the classifier)

These ask whether the classifier can see enough signal to work at all — not what
the customer wants. Order matters: `insufficient_context` runs first, because the
very short cases it removes are exactly where language detection is least reliable.

| Filter | Trigger | Action |
|---|---|---|
| `insufficient_context` | ≤2 words after stripping `<MENTION>`/`<URL>`, OR references off-platform content (a DM/screenshot) with no visible substance | **`clarify`** — ask for more detail. Not auto-handle, not escalation. No reason code. |
| `non_english` | Language detector confidence says not English | **`escalate`** with reason code `out_of_scope` |

**`insufficient_context` examples**

- `850172` *(in open-coding sample)* — “@SpotifyCares :( https://t.co/6uPQ0oIOKv”
- `1251411` *(in open-coding sample)* — “@SpotifyCares check dm please”

A deflection only counts as *insufficient* when nothing else is present. A tweet
that says “check your dms??? my account has been hacked and I’ve been trying
to get help for a week” has ample substance and must reach the classifier as
`account_compromise` — it is **not** filtered.

**`non_english` examples**

- `1350844` *(in open-coding sample)* — “@118266 Kenapa spotify premium saya belum aktif ya? Padahal sudah melunasi pembayaran dan dapat email buktinya.”
- `323490` — “porque é que o support do spotify não me responde caralho”

---

## The 12 substantive intents

### `playback_error`

Audio fails to play, stutters, wrong format

**Examples**

- `1874693` *(in open-coding sample)* — “"can't play the current song" well fuck you then @115888”
- `36734` — “@SpotifyCares any idea why Spotify premium keeps saying ‘cannot play song’ on multiple tracks and artists?”


### `app_platform_bug`

App/UI crash, device sync, platform-specific bug

**Examples**

- `228277` — “@SpotifyCares Android version 8.4.22.857 crashes every time I select "Share"”
- `726004` — “@SpotifyCares (Android 8.0, Pixel) App crashes when trying to share playlist.”


### `account_access`

Can't log in, forgot password, logged out unexpectedly

**Examples**

- `715300` *(in open-coding sample)* — “@SpotifyCares Forgotten my password, but I don't have access to my email linked to my account to reset my password. What can i do?”
- `1355086` *(in open-coding sample)* — “@SpotifyCares Hi. This happens when trying to reset password. Using email or username. https://t.co/WLONMKh137”


### `account_compromise`

Account taken over / modified without consent — semantic intent, not keyword-triggered (many don't say 'hacked')

**Examples**

- `944974` *(in open-coding sample)* — “@SpotifyCares someone changed the email on my account. I mailed on the account, could you look at it?”
- `1870488` *(in open-coding sample)* — “@115888 somebody hacked my account and changed my email”


### `billing_charge_dispute`

Wrong amount charged, charged twice, charged after cancelling

**Examples**

- `1785736` *(in open-coding sample)* — “@SpotifyCares good morning from Atlantic 🇨🇦. Noticed that I'm being charged twice for my account. 9.99$ and 14.99$. Can you help?”
- `621434` — “@115888 I got charged twice in September. Can you please help refund this money back. Thanks”


### `premium_activation_failure`

Paid but Premium features not active / reverted to basic

**Examples**

- `963744` — “@117153 I have paid for Spotify premium but I am still a free member. Help please.”
- `1100181` — “@spotifycares paid 4 premium still ads &amp; listed as free. Logged in and out several times Payment not pending in bank funds withdrawn”


### `student_discount_billing`

Student verification (NUS/UNiDAYS) specifically

**Examples**

- `1035812` *(in open-coding sample)* — “@SpotifyCares hi I'm currently paying £14.99 but I'm now a student, how can I apply for a student account?”
- `1864224` *(in open-coding sample)* — “@SpotifyCares can I get a student discount with just my NUS card? I do not have a unidays”


### `family_plan_management`

Adding/removing family members, individual<->family plan changes

**Examples**

- `1883269` *(in open-coding sample)* — “@115888 Hey! I'm trying to add a family member to my account, but it's giving me an error: "600 - Oops something went wrong." Can you help?”
- `1521344` *(in open-coding sample)* — “@SpotifyCares I'd like to upgrade my premium to a family plan. I paid for the year at once... is it still $14.99/month on top of that?”


### `cancellation_request`

Explicit ask to cancel/unsubscribe

**Examples**

- `1801751` *(in open-coding sample)* — “@115888 help me cancel my premium subscription. When I log into my account it turns the language Russian and I don't speak Russia.....”
- `407161` — “@SpotifyCares I can't cancel my premium, there's nothing under the "account" part where I think cancel should be? Please help https://t.co/LVp1kA0rJi”


### `content_availability`

Specific song/album/artist missing, licensing-related

**Examples**

- `789476` *(in open-coding sample)* — “@115888 PUT AGUST D BACK ON SPOTIFY!! YOU TOOK IT OFF FOR NO REASON!!!”
- `370271` — “@116130 Why is Chris Rea’s Driving Home for Christmas not on Spotify, you’ve ruined Christmas! https://t.co/ylvbZ0M6gT”


### `playlist_issue`

Playlist deleted/altered, curation complaints, shuffle randomness

**Examples**

- `782913` *(in open-coding sample)* — “Spotify has deleted my '90s hip-hop playlist. Oh well. No Biggie.”
- `38955` — “@SpotifyCares Hi, I logged out of my Spotify last week. I logged back in the next day and my playlists have gone. Can you help? Thanks!”


### `feature_complaint`

Wants functionality that doesn't exist

**Examples**

- `227487` — “There should be a way to search songs on your playlist @115888 🎶”
- `211139` — “@115888 please add the ability to have a "Stop" button, that can be right clicked and "Stop playback after current song" be an option?”


---

## The 2 catch-alls

Both are real labels, not fallbacks of last resort for lazy annotation. Neither
names a problem with a resolution path, which is why they sit outside the “12”.

### `venting_no_request`

No actionable ask — praise or pure complaint

**Examples**

- `2220683` *(in open-coding sample)* — “@SpotifyCares that's dope. You're awesome! https://t.co/qi3UN271zq”
- `265069` — “@115888 really means it when they say they care! @SpotifyCares Thank you so much for helping me today!”


### `other`

Genuinely doesn't fit above (artist/upload support, misc)

**Examples**

- `930090` *(in open-coding sample)* — “@115888 how can I upload music on your site?”
- `936220` — “@SpotifyCares Hey guys! I have an artist account and there's another artist being linked with my user. How should we procceed?.”


---

## Tie-break rules

Apply **in order**; stop at the first that resolves.


1. **Multiple intents present** → label the one the customer explicitly asks to be fixed.
2. **No explicit ask** → label the one the brand must action first.
3. **Still tied** → the primary is whichever intent ranks higher in
   **`INTENT_PRIORITY`** (table below). This is **mechanical, not a judgment call**.
   Set `multi_intent=true` and **name the secondary intent in `notes`**.
   *Replaced a judgment-based rule (“label the more escalation-worthy”) after the
   agreement study showed it produced 0/10 reproducibility on multi-intent cases —
   two passes applying it to the same case picked different primaries every time.*
4. **`content_availability` vs `playlist_issue` vs `feature_complaint`:**
   availability = a specific work is missing (licensing); playlist = something
   curated/saved was lost or changed; feature = functionality that never existed
   is being requested.
5. **`billing_charge_dispute` vs `premium_activation_failure`:** billing = the
   charge itself is wrong; activation = the charge was correct but the paid
   feature isn't working — **different resolution owners (finance vs. technical)**.
6. **Genuinely unclassifiable** → `other`. Cap at ~5% of the golden set; if it
   exceeds that, the taxonomy is missing a category.

### Intent priority ordering (`INTENT_PRIORITY`)

Source of truth is `src/data/taxonomy.py`. Read top-down and take the first intent
that is present in the case.

| Rank | Intent |
|---|---|
| 1 | `account_compromise` |
| 2 | `billing_charge_dispute` |
| 3 | `premium_activation_failure` |
| 4 | `account_access` |
| 5 | `cancellation_request` |
| 6 | `student_discount_billing` |
| 7 | `family_plan_management` |
| 8 | `playback_error` |
| 9 | `app_platform_bug` |
| 10 | `playlist_issue` |
| 11 | `content_availability` |
| 12 | `feature_complaint` |
| 13 | `venting_no_request` |
| 14 | `other` |

Ordering principle: **security → financial → access → account admin → technical →
informational → no-action.** Anything requiring a human or a movement of money
outranks any product complaint — a compromised account or a wrong charge accrues
cost while it waits; a missing feature does not.

**Worked example.** A tweet saying the playlists vanished *and* the account email was
changed carries both `playlist_issue` (rank 10) and `account_compromise` (rank 1).
Primary is `account_compromise`; `multi_intent=true`; notes record the secondary.

### Worked application of rule 4

`782913` — “Spotify has deleted my '90s hip-hop playlist. Oh well. No Biggie.”
Something curated was lost, so `playlist_issue`, not `content_availability`. The
songs are still licensed; the saved collection is what went missing.

`789476` — “PUT AGUST D BACK ON SPOTIFY!! YOU TOOK IT OFF FOR NO REASON!!!”
A specific work is gone from the catalogue, so `content_availability`. Note this
is shouted in all caps and still carries no escalation reason code — see
“Explicitly NOT built” below.

---

## Escalation reason codes

An **independent axis** from intent. A case can carry any intent plus any
applicable reason code; these are not mutually exclusive with the intent label.

| Reason code | Trigger | Notes |
|---|---|---|
| `account_compromise` | Intent = `account_compromise` (any phrasing, not just “hacked”) | Always escalate — **semantic** detection, not keyword |
| `fraud_or_billing_dispute` | Unauthorized charge, disputed authorization (e.g. company card used without consent) | **NOT** triggered by words like “theft”/“steal” alone — those are often rhetorical in refund requests. Triggered by the underlying claim, verified via case content, not vocabulary |
| `bereavement_or_sensitive` | Death, grief, or other high-sensitivity personal disclosure | Escalate **and** shift reply tone — suppress default cheerful/emoji templates for this case |
| `low_confidence` | Classifier confidence below calibrated threshold | Standard confidence gate |
| `multi_intent` | Tie-break rule 3 fired | Human resolves which intent takes priority |
| `repeat_contact` | Case references a prior unresolved contact (“you’ve seen this before”, “it’s been a week”) | **Not detectable by this system** — case unit is single-tweet, no memory across contacts. Documented as a stated non-goal / future-work item, **not built** |
| `out_of_scope` | `non_english` filter fired, or other declared non-goal | — |
| `human_requested` | Customer explicitly asks for a phone number, a human, or “an actual person” | Escalate **regardless of underlying intent or confidence** — the literal request is the trigger. **Added after reviewing the golden set** — not present in the original open-coding pass |

`account_compromise` is the one label that is deliberately **both** an intent and a
reason code. That is intentional, not a modelling slip: the intent says what the
case is about, the reason code says it must reach a human.

**Semantic, not keyword.** `944974` — “someone changed the email on my account.
I mailed on the account, could you look at it?” — never says “hacked” and is a
textbook `account_compromise`. Any detector keyed on the word would miss it.

---


## Explicitly NOT built

State in report, do not attempt.

- Profanity/all-caps as an escalation trigger. Confirmed false-positive risk from
  real data (e.g. "STOP DELETING ALL MY SONGS... WHAT THE FUCK DO I PAY FOR" is an
  ordinary bug complaint, not abuse — abuse would be a threat directed at a person,
  which did not appear in the 200-case sample). Escalate on *intent + reason code*,
  never on tone/language alone.
- "Theft"/"fraud" keyword-triggered escalation. Same false-positive class — these
  words appear in ordinary refund requests. `fraud_or_billing_dispute` triggers on
  the underlying claim, not the vocabulary used to describe it.
- Phone/call-center routing. Out of scope entirely — this project has no telephony.
  "Escalate" means: flag the case, attach a reason code, hand to a human review
  queue. Nothing about actual phone transfer is built or claimed.
- Repeat-contact detection. No cross-case memory exists in this system's design
  (single-tweet case unit). Named as a limitation, not partially implemented.


### Why the profanity rule matters in practice

`1874693` — ““can't play the current song” well fuck you then @115888” — is an
ordinary `playback_error` with no reason code. Escalating it on profanity would
burn a human review slot on a routine bug report. Abuse would mean a threat
directed at a person, which did not appear in the 200-case sample.

---

## Third action branch: `clarify`

Cases hitting `insufficient_context` get a **clarifying-question response** — the
system asks for more detail (e.g. “Could you tell us a bit more about what's
happening?”). This is a legitimate third branch in the escalation policy, **not a
compromise** between auto-handle and escalate, and it carries no escalation reason
code.
