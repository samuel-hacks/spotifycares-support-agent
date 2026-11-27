# SpotifyCares Taxonomy — LOCKED

Derived from: Stage 2 clustering (k=8/10/12 comparison) + 200-case manual open-coding
+ escalation design review. This is the taxonomy referenced going forward — do not
re-derive from clustering again.

## Pre-classification routing filters (NOT intents — run before the classifier)

| Filter | Trigger | Action |
|---|---|---|
| `insufficient_context` | ≤2 words after stripping `<MENTION>`/`<URL>`, OR references off-platform content (a DM/screenshot) with no visible substance (e.g. "check dm please", "help me please") | Route to a **clarifying-question response** (ask for more detail), not auto-handle, not full escalation |
| `non_english` | Language detector confidence says not English | Escalate — out of scope per Stage 0 |

These are structurally different from intents: they're about whether the classifier
can even see enough signal to work, not about what the customer wants.

## Intent taxonomy (12 classes)

| Intent | Definition | Example |
|---|---|---|
| `playback_error` | Audio fails to play, stutters, wrong format | "can't play the current song" |
| `app_platform_bug` | App/UI crash, device sync, platform-specific bug | "app doesn't let me browse" |
| `account_access` | Can't log in, forgot password, logged out unexpectedly | "I've tried resetting the password but get nothing in my email" |
| `account_compromise` | Account taken over / modified without consent — **semantic intent, not keyword-triggered** (many don't say "hacked") | "someone changed the email on my account" |
| `billing_charge_dispute` | Wrong amount charged, charged twice, charged after cancelling | "charged twice this month" |
| `premium_activation_failure` | Paid but Premium features not active / reverted to basic | "still not getting premium after several login attempts" |
| `student_discount_billing` | Student verification (NUS/UNiDAYS) specifically | "how can I apply for a student account" |
| `family_plan_management` | Adding/removing family members, individual↔family plan changes | "trying to add a family member, getting an error" |
| `cancellation_request` | Explicit ask to cancel/unsubscribe | "help me cancel my premium subscription" |
| `content_availability` | Specific song/album/artist missing, licensing-related | "why isn't this album streaming" |
| `playlist_issue` | Playlist deleted/altered, curation complaints, shuffle randomness | "my '90s playlist got deleted" |
| `feature_complaint` | Wants functionality that doesn't exist | "queue isn't visible in the app" |
| `venting_no_request` | No actionable ask — praise or pure complaint | "that's dope, you're awesome" |
| `other` | Genuinely doesn't fit above (artist/upload support, misc) | "how do I upload music to your site" |

## Tie-break rules (ordered, apply in sequence)

1. Multiple intents present → label the one the customer explicitly asks to be fixed
2. No explicit ask → label the one the brand must action first
3. Still tied → the primary is whichever intent ranks higher in `INTENT_PRIORITY`.
   This is mechanical, not a judgment call. Set `multi_intent=true` and name the
   secondary intent in the notes. Replaced a judgment-based rule (“label the more
   escalation-worthy”) after the agreement study showed it produced 0/10
   reproducibility on multi-intent cases.
4. `content_availability` vs `playlist_issue` vs `feature_complaint`: availability = a
   specific work is missing (licensing); playlist = something curated/saved was
   lost or changed; feature = functionality that never existed is being requested
5. `billing_charge_dispute` vs `premium_activation_failure`: billing = the charge
   itself is wrong; activation = the charge was correct but the paid feature isn't
   working — different resolution owners (finance vs. technical)
6. Genuinely unclassifiable → `other` (cap at ~5% of golden set; if it exceeds that,
   the taxonomy is missing a category)

## Intent priority ordering (resolves tie-break rule 3)

Defined in `src/data/taxonomy.py` as `INTENT_PRIORITY`; that list is the source of
truth. Ordering principle: security → financial → access → account admin → technical
→ informational → no-action. Anything requiring a human or a movement of money
outranks any product complaint.

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

## Escalation reason codes (independent axis from intent — a case can have any intent
## + any applicable reason code; these are not mutually exclusive with the intent label)

| Reason code | Trigger | Notes |
|---|---|---|
| `account_compromise` | Intent = `account_compromise` (any phrasing, not just "hacked") | Always escalate — semantic detection, not keyword |
| `fraud_or_billing_dispute` | Unauthorized charge, disputed authorization (e.g. company card used without consent) | NOT triggered by words like "theft"/"steal" alone — those are often rhetorical in refund requests. Triggered by the underlying claim (unauthorized use), verified via case content, not vocabulary |
| `bereavement_or_sensitive` | Death, grief, or other high-sensitivity personal disclosure | Escalate AND shift reply tone — suppress default cheerful/emoji templates for this case |
| `low_confidence` | Classifier confidence below calibrated threshold | Standard confidence gate |
| `multi_intent` | Tie-break rule 3 fired | Human resolves which intent takes priority |
| `repeat_contact` | Case references a prior unresolved contact ("you've seen this before", "it's been a week") | **Not detectable by this system** — case unit is single-tweet, no memory across contacts. Documented as a stated non-goal / future-work item, not built |
| `out_of_scope` | `non_english` filter fired, or other declared non-goal | — |
| `human_requested` | Customer explicitly asks for a phone number, a human, or "an actual person" | Escalate **regardless of underlying intent or confidence** — the literal request is the trigger |

## Explicitly NOT built (state in report, do not attempt)

- **Profanity/all-caps as an escalation trigger.** Confirmed false-positive risk from
  real data (e.g. "STOP DELETING ALL MY SONGS... WHAT THE FUCK DO I PAY FOR" is an
  ordinary bug complaint, not abuse — abuse would be a threat directed at a person,
  which did not appear in the 200-case sample). Escalate on *intent + reason code*,
  never on tone/language alone.
- **"Theft"/"fraud" keyword-triggered escalation.** Same false-positive class — these
  words appear in ordinary refund requests. `fraud_or_billing_dispute` triggers on
  the underlying claim, not the vocabulary used to describe it.
- **Phone/call-center routing.** Out of scope entirely — this project has no
  telephony. "Escalate" means: flag the case, attach a reason code, hand to a human
  review queue. Nothing about actual phone transfer is built or claimed.
- **Repeat-contact detection.** No cross-case memory exists in this system's design
  (single-tweet case unit). Named as a limitation, not partially implemented.

## Third action type (beyond auto-handle / escalate)

Cases hitting `insufficient_context` get a **clarifying-question response**, not a
full auto-handle reply and not a full human escalation — the system asks for more
detail (e.g. "Could you tell us a bit more about what's happening?"). This is a
legitimate third branch in the escalation policy, not a compromise between the other two.
