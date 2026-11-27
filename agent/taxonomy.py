"""The SpotifyCares intent taxonomy, as config.

Single source of truth for intent names, pre-filters, escalation reason codes and the
tie-break rules. Nothing downstream should hard-code a label string; import from here.

Provenance: ported from the September project (reference/september/taxonomy_locked.md,
14 labels from clustering + 200-case open coding + an escalation design review), with
the Day 2 changes recorded in DECISIONS.md (2026-11-27, "Taxonomy v2"):

* ``artist_creator`` added (was inside ``other``), priority rank 13.
* ``insufficient_context`` is now also a learned label, not only a rule pre-filter.
* ``content_availability`` covers region launch / availability.
* ``playlist_issue`` covers Spotify-made playlists (Wrapped / Top Songs, Discover Weekly).

16 labels = 13 substantive intents + 3 non-substantive ones
(``venting_no_request``, ``insufficient_context``, ``other``).

Thresholds are NOT defined here. The September version had CONFIDENCE_THRESHOLD and
CLARIFY_MARGIN tuned on the golden set; in this project the golden set is never used
for tuning, so thresholds are tuned on the val split in agent/router.py (Day 4).
"""

from __future__ import annotations

import re

TAXONOMY_VERSION = "v2-2026-11-27"

# --- Intents ------------------------------------------------------------------

#: A real customer problem with a resolution path.
SUBSTANTIVE_INTENTS: list[str] = [
    "playback_error",
    "app_platform_bug",
    "account_access",
    "account_compromise",
    "billing_charge_dispute",
    "premium_activation_failure",
    "student_discount_billing",
    "family_plan_management",
    "cancellation_request",
    "content_availability",
    "playlist_issue",
    "feature_complaint",
    "artist_creator",
]

#: Real labels, but none names a problem to fix.
NON_SUBSTANTIVE_INTENTS: list[str] = [
    "venting_no_request",
    "insufficient_context",
    "other",
]

#: The full classifier label space.
INTENTS: list[str] = SUBSTANTIVE_INTENTS + NON_SUBSTANTIVE_INTENTS

INTENT_DEFINITIONS: dict[str, str] = {
    "playback_error": "Audio fails to play, stutters, wrong format",
    "app_platform_bug": "App/UI crash, device sync, platform-specific bug",
    "account_access": "Can't log in, forgot password, logged out unexpectedly",
    "account_compromise": (
        "Account taken over / modified without consent. Semantic intent, not "
        "keyword-triggered (many don't say 'hacked')"
    ),
    "billing_charge_dispute": "Wrong amount charged, charged twice, charged after cancelling",
    "premium_activation_failure": "Paid but Premium features not active / reverted to basic",
    "student_discount_billing": "Student verification (NUS/UNiDAYS) specifically",
    "family_plan_management": "Adding/removing family members, individual<->family plan changes",
    "cancellation_request": "Explicit ask to cancel/unsubscribe",
    "content_availability": (
        "Specific song/album/artist/podcast missing or greyed out (licensing), or Spotify "
        "not launched / not available in the customer's country or region"
    ),
    "playlist_issue": (
        "Playlist deleted/altered, curation complaints, shuffle randomness, and "
        "Spotify-made playlists (Wrapped / Your Top Songs, Discover Weekly, Daily Mix, "
        "Release Radar): missing, late or wrong"
    ),
    "feature_complaint": "Wants functionality that doesn't exist",
    "artist_creator": (
        "Asked by an artist/label about their own presence: verification, getting music "
        "on Spotify, Spotify for Artists, royalties, their release under the wrong artist"
    ),
    "venting_no_request": "No actionable ask: praise or pure complaint",
    "insufficient_context": (
        "No identifiable issue: generic help request ('can u help me'), a check on a DM "
        "or earlier message, or emotion/an image with no subject"
    ),
    "other": "Identifiable issue that genuinely fits no label above",
}

# --- Intent priority (tie-break rule 3) ---------------------------------------

#: Index 0 is highest priority. security -> financial -> access -> account admin ->
#: technical -> informational -> creator -> no-action -> unreadable -> unclassifiable.
#:
#: Replaced a judgment rule ("label the more escalation-worthy") after the September
#: agreement study showed 0/10 reproducibility on multi-intent cases.
#:
#: insufficient_context sits below venting_no_request because it is defined by the
#: absence of a readable issue: if any intent can be read, even praise, the context is
#: not insufficient, so every real intent must win a tie. It sits above other because
#: other claims there IS an issue that no label fits; when an annotator wavers between
#: "nothing visible" and "something unplaceable", the clarifying question recovers
#: information while other has no resolution path.
INTENT_PRIORITY: list[str] = [
    "account_compromise",          # 1  security: someone else is in the account
    "billing_charge_dispute",      # 2  financial: money moved incorrectly
    "premium_activation_failure",  # 3  financial: money moved, value not delivered
    "account_access",              # 4  access: locked out of what they own
    "cancellation_request",        # 5  account admin: explicit instruction to act
    "student_discount_billing",    # 6  account admin: entitlement verification
    "family_plan_management",      # 7  account admin: membership changes
    "playback_error",              # 8  technical: core product not working
    "app_platform_bug",            # 9  technical: client defect
    "playlist_issue",              # 10 technical: user data altered or lost
    "content_availability",        # 11 informational: licensing / region
    "feature_complaint",           # 12 informational: does not exist yet
    "artist_creator",              # 13 creator support: no money or security at stake
    "venting_no_request",          # 14 no action requested
    "insufficient_context",        # 15 nothing readable; ask a question
    "other",                       # 16 no label fits
]


def resolve_primary_intent(intents: list[str]) -> str:
    """Return the highest-priority intent. Raises on unknown labels (no silent default)."""
    if not intents:
        raise ValueError("resolve_primary_intent() requires at least one intent")
    unknown = [i for i in intents if i not in INTENT_PRIORITY]
    if unknown:
        raise ValueError(f"Not in INTENT_PRIORITY: {unknown}")
    return min(intents, key=INTENT_PRIORITY.index)


# --- Pre-classification filters (rules, run before the classifier) -------------

#: insufficient_context is deliberately both a pre-filter (hard rule) and a learned
#: intent (for the cases a rule can't catch). Both lead to the clarify action.
PREFILTERS: list[str] = ["insufficient_context", "non_english"]

PREFILTER_DEFINITIONS: dict[str, str] = {
    "insufficient_context": "<=2 words after stripping placeholders (@user, <URL>)",
    "non_english": "Language detector says not English",
}

MAX_WORDS_INSUFFICIENT = 2

# --- Escalation reason codes --------------------------------------------------

#: Independent axis from intent: a case has one intent and zero or more reason codes.
ESCALATION_REASON_CODES: list[str] = [
    "account_compromise",
    "fraud_or_billing_dispute",
    "bereavement_or_sensitive",
    "low_confidence",
    "multi_intent",
    "repeat_contact",
    "out_of_scope",
    "human_requested",
    "pii",
    "needs_account_action",
    "legal_or_regulatory_threat",
]

ESCALATION_REASON_DEFINITIONS: dict[str, str] = {
    "account_compromise": (
        "Intent = account_compromise (any phrasing, not just 'hacked'). Always escalate."
    ),
    "fraud_or_billing_dispute": (
        "Unauthorized charge or disputed authorization. Triggered by the underlying "
        "claim, not by words like 'theft'/'steal', which are often rhetorical."
    ),
    "bereavement_or_sensitive": (
        "Death, grief or other high-sensitivity personal disclosure. Escalate and drop "
        "the cheerful/emoji tone."
    ),
    "low_confidence": "Classifier confidence below the threshold tuned on val.",
    "multi_intent": "Tie-break rule 3 fired. A human decides which intent comes first.",
    "repeat_contact": (
        "Refers to a prior unresolved contact. NOT detectable: the case unit is one "
        "tweet with no cross-case memory. Named as a limitation, not built."
    ),
    "out_of_scope": "non_english fired, or another declared non-goal.",
    "human_requested": (
        "Customer asks for a phone number, a human or 'an actual person'. Escalate "
        "regardless of intent or confidence."
    ),
    "pii": (
        "The tweet contains personal data (email, phone, card number, address) or the "
        "only sensible reply would ask for it in public. Added in v2 for spec section 6."
    ),
    "needs_account_action": (
        "Resolving it needs someone to look at or change this specific account (refund, "
        "Premium not active after paying, account recovery, a stuck Family invite), "
        "usually by moving to DM. A public triage question ('which device?') is not this. "
        "Added in v2 for spec section 6."
    ),
    "legal_or_regulatory_threat": (
        "Explicit legal action or a regulator: sue/lawyer/lawsuit, small claims or "
        "consumer court, FTC/BBB/ombudsman/trading standards, a chargeback threat. Never "
        "profanity, capitals, general anger, or rhetorical 'this is criminal/theft'."
    ),
}

#: Narrow on purpose: names of legal actions and regulators only. Tone words are absent
#: by design. Matches whole words ("issue"/"pursue" don't hit "sue"). A chargeback counts
#: only as a threat ("I'll file a chargeback"), not "I received a chargeback". On train it
#: fires on 5 of 20,626 tickets: 2 real threats and 3 jokes, an accepted over-escalation.
LEGAL_THREAT_PATTERN = re.compile(
    r"\b(?:sue|suing|sued|lawsuit|class[- ]action|lawyers?|attorneys?|solicitors?"
    r"|legal action|take (?:you|this|spotify|it|them) to court|small claims"
    r"|consumer (?:court|forum|protection)|ftc|bbb|better business bureau|ombudsman"
    r"|trading standards"
    r"|(?:file|filing|do|doing|issue|request|initiate|open|start) a charge ?back"
    r"|charge ?back (?:with|through) (?:my|the) (?:bank|card))\b",
    re.IGNORECASE,
)


def is_legal_or_regulatory_threat(text: str) -> bool:
    """True only on explicit legal-action or regulator wording (see LEGAL_THREAT_PATTERN)."""
    return bool(LEGAL_THREAT_PATTERN.search(text or ""))

UNIMPLEMENTED_REASON_CODES: list[str] = ["repeat_contact"]

#: Mapping to the spec's router reason codes (spec section 6). The router (Day 4) emits
#: the spec codes; this keeps the two vocabularies linked.
#: Spec ANGRY_OR_RISKY is split into bereavement_or_sensitive + legal_or_regulatory_threat.
#: Tone or profanity alone never escalates (see NOT_BUILT and DECISIONS.md).
SPEC_REASON_CODE: dict[str, str] = {
    "account_compromise": "SENSITIVE_INTENT",
    "fraud_or_billing_dispute": "SENSITIVE_INTENT",
    "bereavement_or_sensitive": "ANGRY_OR_RISKY",
    "low_confidence": "LOW_CONFIDENCE",
    "multi_intent": "LOW_CONFIDENCE",
    "out_of_scope": "OUT_OF_SCOPE",
    "human_requested": "NEEDS_ACCOUNT_ACTION",
    "pii": "PII",
    "needs_account_action": "NEEDS_ACCOUNT_ACTION",
    "legal_or_regulatory_threat": "ANGRY_OR_RISKY",
}

# --- Actions ------------------------------------------------------------------

#: Three branches. clarify is a first-class outcome, not a compromise.
ACTIONS: list[str] = ["auto_handle", "clarify", "escalate"]

#: Default action implied by the intent alone, before confidence/reason-code checks.
INTENT_DEFAULT_ACTION: dict[str, str] = {i: "auto_handle" for i in INTENTS}
INTENT_DEFAULT_ACTION.update(
    {
        "account_compromise": "escalate",
        "billing_charge_dispute": "escalate",
        "insufficient_context": "clarify",
        "other": "escalate",
    }
)

# --- Customer-facing names (raw labels never reach a customer) ----------------

INTENT_DISPLAY_NAMES: dict[str, str] = {
    "playback_error": "music not playing properly",
    "app_platform_bug": "a problem with the app itself",
    "account_access": "trouble signing in",
    "account_compromise": "someone else accessing your account",
    "billing_charge_dispute": "a charge that looks wrong",
    "premium_activation_failure": "Premium not activating after payment",
    "student_discount_billing": "the student discount",
    "family_plan_management": "your Family plan",
    "cancellation_request": "cancelling your subscription",
    "content_availability": "a song, album or Spotify itself not being available",
    "playlist_issue": "a problem with your playlists",
    "feature_complaint": "a feature you'd like us to add",
    "artist_creator": "your music or artist profile on Spotify",
    "venting_no_request": "general feedback",
    "insufficient_context": "what's going on",
    "other": "something else",
}

# --- Rules --------------------------------------------------------------------

TIE_BREAK_RULES: str = """\
1. Multiple intents present -> label the one the customer explicitly asks to be fixed.
2. No explicit ask -> label the one the brand must action first.
3. Still tied -> the higher one in INTENT_PRIORITY. Mechanical, not a judgment call.
   Set multi_intent=true and name the secondary intent in notes.
4. content_availability vs playlist_issue vs feature_complaint: availability = a
   specific work (or Spotify itself, by region) is missing; playlist = something
   curated/saved, or a Spotify-made playlist, was lost, changed or is late; feature =
   functionality that never existed.
5. billing_charge_dispute vs premium_activation_failure: billing = the charge itself is
   wrong; activation = the charge was right but Premium isn't working.
6. artist_creator vs content_availability: the artist asking about their own music is
   artist_creator; a listener asking where a song went is content_availability.
7. insufficient_context vs venting_no_request: any readable praise or complaint about
   a named thing is venting_no_request; nothing readable is insufficient_context.
8. Genuinely unclassifiable -> other. Cap ~5% of the golden set; above that the
   taxonomy is missing a category.
"""

NOT_BUILT: str = """\
- Profanity/all-caps/anger as an escalation trigger. Escalate on intent + reason code,
  never on tone or language alone. (legal_or_regulatory_threat fires on named legal
  actions and regulators, not on tone.)
- "Theft"/"fraud" keyword-triggered escalation. fraud_or_billing_dispute triggers on
  the underlying claim, not the vocabulary.
- Phone/call-center routing. "Escalate" means flag + reason code + human queue.
- Repeat-contact detection. Single-tweet case unit, no cross-case memory.
"""


def validate() -> None:
    """Fail loudly on a taxonomy that contradicts itself."""
    assert len(SUBSTANTIVE_INTENTS) == 13, len(SUBSTANTIVE_INTENTS)
    assert len(NON_SUBSTANTIVE_INTENTS) == 3, len(NON_SUBSTANTIVE_INTENTS)
    assert len(INTENTS) == len(set(INTENTS)) == 16, INTENTS
    assert len(INTENT_PRIORITY) == len(set(INTENT_PRIORITY)) == 16
    assert set(INTENT_PRIORITY) == set(INTENTS)
    assert INTENT_PRIORITY.index("artist_creator") == 12  # rank 13
    assert (
        INTENT_PRIORITY.index("venting_no_request")
        < INTENT_PRIORITY.index("insufficient_context")
        < INTENT_PRIORITY.index("other")
    )
    assert set(INTENT_DEFINITIONS) == set(INTENTS)
    assert set(INTENT_DISPLAY_NAMES) == set(INTENTS)
    assert set(INTENT_DEFAULT_ACTION) == set(INTENTS)
    assert set(INTENT_DEFAULT_ACTION.values()) <= set(ACTIONS)
    assert set(PREFILTER_DEFINITIONS) == set(PREFILTERS)
    assert set(ESCALATION_REASON_DEFINITIONS) == set(ESCALATION_REASON_CODES)
    assert set(UNIMPLEMENTED_REASON_CODES) <= set(ESCALATION_REASON_CODES)
    assert set(SPEC_REASON_CODE) | set(UNIMPLEMENTED_REASON_CODES) == set(ESCALATION_REASON_CODES)
    # The only deliberate overlap between intents and pre-filters.
    assert set(INTENTS) & set(PREFILTERS) == {"insufficient_context"}


validate()


if __name__ == "__main__":
    print(f"taxonomy {TAXONOMY_VERSION}: {len(INTENTS)} labels")
    for rank, name in enumerate(INTENT_PRIORITY, 1):
        print(f"  {rank:>2} {name:<28} -> {INTENT_DEFAULT_ACTION[name]}")
