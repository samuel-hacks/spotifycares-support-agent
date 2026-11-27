# Data card: SpotifyCares ticket/reply pairs

Source: Kaggle "Customer Support on Twitter" (`twcs.csv`), brand account `SpotifyCares`. Built by `make data` (`data/prepare.py`).

## How pairs were built

- A ticket is the first customer tweet of a conversation (the thread root).
- The paired reply is the first SpotifyCares tweet that answers that root directly.
- Ticket text: brand mentions (`@SpotifyCares`, `@115888` = anonymised @Spotify) removed, URLs -> `<URL>`, other mentions -> `@user`, HTML entities unescaped, emojis kept.
- Reply text: leading @recipient, `1:` part markers, agent signature (`/NJ`, `^JD`) and the trailing DM link removed. Real URLs are kept in `reply_text`; `reply_clean` has `<URL>`. The signature is stored in `reply_signature`.
- Exact-duplicate tickets removed (earliest kept). Tickets with no letters dropped.
- Time split on ticket `created_at`: oldest 80% train, next 10% val, newest 10% test.

## Build funnel

| step | count |
|---|---:|
| brand_replies | 43,265 |
| conversations | 28,280 |
| conversations_with_customer_root | 28,221 |
| conversations_with_direct_reply | 26,094 |
| dropped_empty | 133 |
| dropped_duplicates | 64 |
| pairs | 25,897 |

## Splits

| split | pairs | from | to |
|---|---:|---|---|
| train | 20,717 | 2014-05-15 23:34 | 2017-11-22 17:02 |
| val | 2,589 | 2017-11-22 17:02 | 2017-11-28 20:56 |
| test | 2,591 | 2017-11-28 20:56 | 2017-12-03 22:07 |

## Lengths

| field | mean chars | mean words | median words | max words |
|---|---:|---:|---:|---:|
| ticket_text | 99 | 18.7 | 18 | 59 |
| reply_text | 114 | 20.2 | 20 | 54 |

- Replies with an agent signature: 97.3% (204 distinct initials)
- Replies ending in a DM link: 28.9%
- Conversations with more than two tweets: 31.9%

## Language mix (langdetect on ticket_text, seed 0)

| lang | share |
|---|---:|
| en | 95.3% |
| id | 0.9% |
| fr | 0.4% |
| de | 0.4% |
| nl | 0.3% |
| tl | 0.3% |
| af | 0.3% |
| cy | 0.3% |
| sv | 0.2% |
| so | 0.2% |

## Examples (random, seed 7)

- **[train] ticket:** WTF ?! Stop eating my mobile data, please. There's a reason I have premium to download songs... <URL>
  **reply:** Hey there! Can you let us know the Android and Spotify versions you're using? We'll see what we can suggest
- **[test] ticket:** Hey can y’all activate my premium. Or can I have my money back?
  **reply:** Hey there, help's here! Can you DM us your account's email address/username? We'll check backstage
- **[train] ticket:** oh the spotify app is set to be a an automatic login item how annoying
  **reply:** Hey there! Can you give us more info on what's happening? We'll see what we can suggest
- **[train] ticket:** Podcast episode progress do not sync cross devices. 😰 Is this a known issue?
  **reply:** Hi Erik, help's here! Can you let us know the devices you're using, their operating systems, and Spotify versions? We'll see what we can suggest
- **[train] ticket:** #RapCavier ? Details
  **reply:** Hey there! Can you let us know how we can help?
- **[train] ticket:** my name couldn't be confirmed for spotify student but i still got charged. when do i get my money back?
  **reply:** Hey there! Can you DM us your account's email address and username? We'll take a look backstage

## Known caveats

- Twitter user IDs are anonymised in the source data, so `@user` replaces all handles.
- Almost all data is from Oct to Dec 2017; a few older threads exist. The split is by time, so the test window is the most recent ~10% (early Dec 2017).
- The first reply is often a triage question ("which device?") rather than a fix; this matters for drafting and routing.
