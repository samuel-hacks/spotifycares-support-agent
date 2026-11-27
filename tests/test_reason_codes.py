import pytest

from agent.taxonomy import (
    ESCALATION_REASON_CODES,
    SPEC_REASON_CODE,
    is_legal_or_regulatory_threat,
)


def test_legal_code_is_registered_and_maps_to_angry_or_risky():
    assert "legal_or_regulatory_threat" in ESCALATION_REASON_CODES
    assert SPEC_REASON_CODE["legal_or_regulatory_threat"] == "ANGRY_OR_RISKY"
    assert SPEC_REASON_CODE["bereavement_or_sensitive"] == "ANGRY_OR_RISKY"


@pytest.mark.parametrize(
    "text",
    [
        "Fix this or I'm suing y'all",
        "Maybe if a lawyer was involved you might get back with me?",
        "I'm filing a lawsuit over these charges",
        "see you in small claims court",
        "reporting you to the FTC and the BBB",
        "I've contacted the ombudsman about this",
        "going to trading standards with this",
        "I will file a chargeback with my bank",
        "doing a charge back through my card if this isn't fixed",
        "we'll take you to court",
        "my attorney will be in touch",
    ],
)
def test_legal_threats_fire(text):
    assert is_legal_or_regulatory_threat(text)


@pytest.mark.parametrize(
    "text",
    [
        "this is criminal",
        "Having a censored version of To Pimp A Butterfly is a crime.",
        "It's theft can you reimburse me",
        "WHAT THE FUCK DO I PAY FOR, FIX YOUR APP",
        "I'm cancelling and going to Apple Music",
        "there is an issue with my account",
        "I will pursue this until it's fixed",
        "I just received a chargeback for a gift card, why?",
        "the courtesy of a reply would be nice",
        "",
    ],
)
def test_tone_and_rhetoric_do_not_fire(text):
    assert not is_legal_or_regulatory_threat(text)
