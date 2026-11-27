# SpotifyCares labelling guide (taxonomy v2)

This is how to fill in `eval/golden_labeling.csv`. It is built from the September guide and `reference/september/taxonomy_locked.md`, updated for taxonomy v2 (`agent/taxonomy.py`, version `v2-2026-11-27`). The label strings in `agent/taxonomy.py` are the source of truth.

Every example below is a real ticket from the **train** split, shown the way it appears in the `text` column (brand mention removed, `@user`, `<URL>`). None come from the test window and none are golden rows, so reading this guide can't leak anything into the golden set.

## The labelling sheet

One row per ticket. Fill these columns:

| column | values |
|---|---|
| `gold_intent` | one of the 16 intents below, or `non_english` |
| `multi_intent` | `true` if tie-break rule 3 decided it, otherwise leave empty |
| `gold_route` | `auto`, `clarify` or `escalate` |
| `gold_reason` | reason codes for `escalate`, separated by `;` (empty for `auto` and `clarify`) |
| `annotator_confidence` | 1 (unsure), 2, or 3 (sure) |
| `notes` | anything useful: the secondary intent, why it was hard |

Label blind. The sheet has no model predictions and doesn't show the real SpotifyCares reply, because seeing either would pull the label towards it. Don't look anything up in `data/` while labelling.

`python -m eval.sample_golden build` checks every value and writes `eval/golden.jsonl`.

## Order of decisions

1. **Pre-filters.** Is the tweet 2 words or fewer once `@user` and `<URL>` are removed? Then it's `insufficient_context` / `clarify`. Is it not in English? Then it's `non_english` / `escalate` / `out_of_scope`.
2. **Intent.** Pick one using the definitions and the tie-break rules.
3. **Route and reasons.** Apply the routing rules. Reason codes are a separate axis from intent: any intent can carry any applicable reason code.

## Pre-filters

| filter | trigger | label |
|---|---|---|
| `insufficient_context` (rule) | 2 words or fewer after removing `@user` / `<URL>` | `insufficient_context`, route `clarify`, no reason code |
| `non_english` | not English | `non_english`, route `escalate`, reason `out_of_scope` |

`insufficient_context` is also a normal intent for longer tweets with no identifiable issue (see below). Both paths lead to the same clarifying-question response.

**non_english examples**

- `1350844`: "@user Kenapa spotify premium saya belum aktif ya? Padahal sudah melunasi pembayaran dan dapat email buktinya."
- `323490`: "porque é que o support do spotify não me responde caralho"

A tweet that mixes in a few non-English words but is readable in English is labelled normally.

## The 16 intents

13 substantive intents, then 3 that name no problem to fix.

### playback_error
Audio fails to play, stutters, skips, or the wrong track plays.

- `1874693`: ""can't play the current song" well fuck you then"
- `36734`: "any idea why Spotify premium keeps saying ‘cannot play song’ on multiple tracks and artists?"

### app_platform_bug
App, web player or website crashes or misbehaves, an outage, downloads vanishing, or Spotify on a device (Alexa/Echo, Sonos, Roku, TV, car, receiver, console) not working.

- `228277`: "Android version 8.4.22.857 crashes every time I select "Share""
- `1844102`: "my amazon echo wont connect to spotify, please help"

### account_access
Can't log in, forgot password, logged out unexpectedly, Facebook login, can't find which email or username the account uses.

- `715300`: "Forgotten my password, but I don't have access to my email linked to my account to reset my password. What can i do?"
- `1355086`: "Hi. This happens when trying to reset password. Using email or username. <URL>"

### account_compromise
Someone else is using or has changed the account. This is about meaning, not keywords: many of these never say "hacked".

- `944974`: "someone changed the email on my account. I mailed on the account, could you look at it?"
- `1870488`: "somebody hacked my account and changed my email"

### billing_charge_dispute
The charge itself is wrong: charged twice, wrong amount, charged after cancelling, unknown charges, refunds.

- `1785736`: "good morning from Atlantic 🇨🇦. Noticed that I'm being charged twice for my account. 9.99$ and 14.99$. Can you help?"
- `621434`: "I got charged twice in September. Can you please help refund this money back. Thanks"

### premium_activation_failure
The charge was right but Premium isn't working: paid and the account still shows free, still getting ads.

- `963744`: "@user I have paid for Spotify premium but I am still a free member. Help please."
- `1100181`: "paid 4 premium still ads & listed as free. Logged in and out several times Payment not pending in bank funds withdrawn"

### student_discount_billing
Student discount, student verification (UNiDAYS, NUS), Student + Hulu.

- `1035812`: "hi I'm currently paying £14.99 but I'm now a student, how can I apply for a student account?"
- `1864224`: "can I get a student discount with just my NUS card? I do not have a unidays"

### family_plan_management
Adding or removing Family members, invites, moving between individual and Family plans.

- `1883269`: "Hey! I'm trying to add a family member to my account, but it's giving me an error: "600 - Oops something went wrong." Can you help?"
- `1521344`: "I'd like to upgrade my premium to a family plan. I paid for the year at once... is it still $14.99/month on top of that?"

### cancellation_request
Wants to cancel or unsubscribe, or asks how cancelling works.

- `1801751`: "help me cancel my premium subscription. When I log into my account it turns the language Russian and I don't speak Russia....."
- `407161`: "I can't cancel my premium, there's nothing under the "account" part where I think cancel should be? Please help <URL>"

### content_availability
A listener wants a song, album, artist or podcast that is missing, removed or greyed out, asks Spotify to add it, or reports wrong song/album info. **v2:** also Spotify not launched or not available in the customer's country.

- `789476`: "PUT AGUST D BACK ON SPOTIFY!! YOU TOOK IT OFF FOR NO REASON!!!"
- `370271`: "@user Why is Chris Rea’s Driving Home for Christmas not on Spotify, you’ve ruined Christmas! <URL>"
- `737841`: "when will spotify come to India?"

### playlist_issue
A playlist or saved library was lost or changed, shuffle repeats the same songs, curation and recommendation complaints. **v2:** also Spotify-made playlists (Wrapped / Your Top Songs 2017, Year in Music, Discover Weekly, Daily Mix, Release Radar) that are missing, late or wrong.

- `782913`: "Spotify has deleted my '90s hip-hop playlist. Oh well. No Biggie."
- `38955`: "Hi, I logged out of my Spotify last week. I logged back in the next day and my playlists have gone. Can you help? Thanks!"
- `2308807`: "when will we get our Top Songs of 2017 playlist?"

### feature_complaint
Asks for functionality that doesn't exist yet.

- `227487`: "There should be a way to search songs on your playlist 🎶"
- `211139`: "please add the ability to have a "Stop" button, that can be right clicked and "Stop playback after current song" be an option?"

### artist_creator (new in v2)
An artist or label asking about their **own** music: verification, their artist page, Spotify for Artists, uploading, distributors, their release showing up under the wrong artist, pitching their music for a playlist.

- `936220`: "Hey guys! I have an artist account and there's another artist being linked with my user. How should we procceed?."
- `930090`: "how can I upload music on your site?"
- `919505`: "Hey guys, do you know how long it takes for a verfication request on Spotify for Artists to go through? Thanks!"

### venting_no_request
Praise, thanks, or a complaint that names no concrete problem and asks for nothing.

- `2220683`: "that's dope. You're awesome! <URL>"
- `265069`: "really means it when they say they care! Thank you so much for helping me today!"

### insufficient_context (a learned label in v2)
No identifiable problem: a generic "help me", "how do I contact someone", "check your DM", or emotion or an image with no subject.

- `1275672`: "please check your DM"
- `19785`: "hi how do I contact someone?"
- `61161`: "Hey I need some help!"

Only use it when nothing else is there. "check your DMs, my account was hacked and nobody has helped me for a week" is `account_compromise`.

### other
A concrete, described request that fits none of the above. It should be rare: if `other` goes above about 5% of the golden set, the taxonomy is missing a category.

- `211122`: "waiting for to send me the pre-sale code for H. E. R. i love her sososososo much"
- `1233745`: "Hi spotify! Where can I find an email address to contact someone about jobs, please?"

## Tie-break rules

Apply in order and stop at the first one that settles it.

1. Several intents present: label the one the customer explicitly asks to be fixed.
2. No explicit ask: label the one the brand has to act on first.
3. Still tied: take the one higher in `INTENT_PRIORITY` (table below). This is mechanical, not a judgement call. Set `multi_intent=true` and name the secondary intent in `notes`. (September replaced a judgement rule with this after an agreement study found 0/10 reproducibility on multi-intent cases.)
4. `content_availability` vs `playlist_issue` vs `feature_complaint`: availability = a specific work (or Spotify itself, by region) is missing; playlist = something curated or saved, or a Spotify-made playlist, was lost, changed or is late; feature = functionality that never existed.
5. `billing_charge_dispute` vs `premium_activation_failure`: billing = the charge is wrong; activation = the charge was right but Premium isn't working. Different owners (finance vs technical).
6. `artist_creator` vs `content_availability`: an artist asking about their own music is `artist_creator`; a listener asking where a song went is `content_availability`.
7. `insufficient_context` vs `venting_no_request`: readable praise or a complaint about something named is `venting_no_request`; nothing readable is `insufficient_context`.
8. Profanity, capitals or anger never change the intent. "your app aint playing any music" with swearing is still `playback_error`.
9. Genuinely unclassifiable: `other`.

## INTENT_PRIORITY

Read from the top and take the first intent present. Order: security, money, access, account admin, technical, informational, creator, no action, unreadable, unclassifiable.

| rank | intent |
|---:|---|
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
| 13 | `artist_creator` |
| 14 | `venting_no_request` |
| 15 | `insufficient_context` |
| 16 | `other` |

`artist_creator` sits at 13 because creator support has no money or security at stake. `insufficient_context` sits at 15: if anything readable is there, even praise, the context isn't insufficient, so every real intent wins a tie. It sits above `other` because a clarifying question recovers information and `other` has no resolution path.

**Worked example.** Playlists vanished *and* the email was changed: `playlist_issue` (10) and `account_compromise` (1). The primary is `account_compromise`, `multi_intent=true`, and `notes` says `playlist_issue`.

## Routing rules (gold_route and gold_reason)

`gold_route` is what a careful human agent would do with this tweet. It is **not** what the model would do.

- **clarify**: the intent is `insufficient_context`. No reason code.
- **escalate**: at least one reason code below applies. List all that apply.
- **auto**: everything else. That includes tickets where the right public reply is a triage question ("which device and app version?") or a known answer from past replies ("that album isn't available yet").

| reason code | use it when | notes |
|---|---|---|
| `account_compromise` | intent is `account_compromise` | always escalate; any phrasing |
| `fraud_or_billing_dispute` | an unauthorised charge or disputed authorisation is claimed | the claim, not the words: "#fraud" on a currency-fee question is not this |
| `bereavement_or_sensitive` | death, grief or another high-sensitivity personal disclosure | the reply tone also changes |
| `multi_intent` | tie-break rule 3 decided the intent | a human picks which issue goes first |
| `out_of_scope` | `non_english`, or intent `other` | `other` has no reply family to ground a draft on |
| `human_requested` | asks for a phone number, a human, "a real person" | escalate whatever the intent |
| `pii` | the tweet contains an email, phone number, card number or address, or the only sensible reply would ask for one in public | new in v2 (spec section 6) |
| `needs_account_action` | resolving it needs someone to look at or change this account: a refund, Premium not active after paying, account recovery, a stuck Family invite, a student check backstage. Usually means "DM us your email" | new in v2 (spec section 6). A public triage question is not this |
| `legal_or_regulatory_threat` | explicit legal action or a regulator: sue / lawyer / lawsuit, small claims or consumer court, FTC / BBB / ombudsman / trading standards, a threat to file a chargeback | new in v2. Never for profanity, capitals, general anger, or rhetorical "this is criminal / theft / a crime". A joke that clearly isn't a threat doesn't count either |
| `low_confidence` | never use in gold labels | model-side only |
| `repeat_contact` | never use in gold labels | not detectable by this system (single-tweet case unit); a named limitation |

`billing_charge_dispute` always escalates (spec: always-human intent): use `fraud_or_billing_dispute` when unauthorised, otherwise `needs_account_action`.

**Examples**

- `875021`: "trying to deal with customer service but its awful. what is a number I can dial to reach a real person????" *(escalate, human_requested)*
- `2250145`: "Love , but hate that they don’t have a phone number that I can call for my questions!! Can y’all give me a call? [phone redacted]" *(escalate, pii; contains a phone number, redacted here)*
- `1810749`: "Hey! My dad died recently with his own Premium account, and we don't have his password. How can I cancel his subscription?" *(escalate, bereavement_or_sensitive; needs_account_action)*
- `963744`: "@user I have paid for Spotify premium but I am still a free member. Help please." *(escalate, needs_account_action)*

- `1520722`: "Fix this or I'm suing y'all asses <URL>" *(escalate, legal_or_regulatory_threat)*
- `2472606`: "You have horrible customer service, been trying for 3 months to get a response from you, you keep charging me for a FREE account, and won't get back to me. Maybe if a lawyer was involved you might get back with me? Spotify you don't CARE!! <URL>" *(escalate, legal_or_regulatory_threat; needs_account_action)*

False positives that stay as they are:

- `211400`: "can we pls have tailored ads for each genre.. I just died a lil when the running workout ad started during my acoustic jams thank u" *(feature_complaint, auto: "died" is slang)*
- `2070814`: "Having a censored version of To Pimp A Butterfly is a crime." *(content_availability, auto: "a crime" is rhetorical, no legal action named)*
- `1270565`: ", if i wake up in the middle of the night to the voice of jigsaw imma sue #yalltrynagiveabrotheraheartattack" *(feature_complaint or venting_no_request, auto: "imma sue" is a joke about an ad)*
- `2497537`: "Wow! Thank you. I appreciate it. I thought I was going to have to catch you guys outside... of the courthouse when I sue you. Such a relief. <URL>" *(venting_no_request, auto: thanks, the "sue you" is a joke about the past)*

The automatic `legal_or_regulatory_threat` rule matches words, so it will fire on jokes like the last two. That's an accepted over-escalation (it fired on 5 of 20,626 train tickets, 2 of them real). Your gold label should follow what the tweet means.

## Explicitly not built

State these in the report and don't label as if they exist:

- **No escalation on tone, profanity, capitals or general anger alone.** Escalate on intent plus reason code only. An all-caps, sweary bug report is an ordinary bug report. The spec's ANGRY_OR_RISKY code is split into `bereavement_or_sensitive` and `legal_or_regulatory_threat`, both of which need a stated fact (a death, a named legal action or regulator), never a tone.
- **No "theft"/"fraud" keyword escalation.** These words show up in ordinary refund requests; `fraud_or_billing_dispute` follows the claim.
- **No phone or call-centre routing.** "Escalate" means: flag it, attach reason codes, hand it to a human queue.
- **No repeat-contact detection.** One tweet is the case unit and there is no memory across contacts.
