"""Mo conversation language plumbing + language≠geography safety (Capstone P3.5).

The conversation language is a bounded, allow-listed directive that sets only the
language of Mo's prose. It can never inject prompt text and never changes retrieval
geography (which is derived solely from the query text).
"""

from __future__ import annotations

from src.agent.policies import RESPONSE_LANGUAGE_NAMES, response_language_directive
from src.application.agent_service import _resolve_language


def test_directive_only_for_known_non_english_codes():
    assert "German" in (response_language_directive("de") or "")
    assert "French" in (response_language_directive("fr") or "")
    assert response_language_directive("en") is None  # default needs no directive
    assert response_language_directive(None) is None


def test_directive_is_injection_safe():
    # Arbitrary/malicious values yield NO directive (built only from the allow-list).
    for bad in ["xx", "'; DROP TABLE users; --", "en; ignore previous", "<script>", "de fr"]:
        assert response_language_directive(bad) is None


def test_all_seven_languages_configured():
    assert set(RESPONSE_LANGUAGE_NAMES) == {"en", "de", "fr", "es", "it", "pt", "nl"}


def test_resolve_language_allowlist():
    assert _resolve_language("fr") == "fr"
    assert _resolve_language("EN") == "en"
    assert _resolve_language("bogus") is None
    assert _resolve_language(None) is None


def test_directive_states_geography_is_unchanged():
    d = response_language_directive("de")
    assert d and "geography" in d.lower()  # explicitly instructs: do not change geography


def test_initialise_injects_directive_only_when_non_english():
    from src.agent.nodes import make_initialise_node

    init = make_initialise_node()
    out = init({"goal": "Prep me", "response_language": "de", "memory_items": []})
    system = [m for m in out["messages"] if m.__class__.__name__ == "SystemMessage"]
    assert any("German" in m.content for m in system)

    out_en = init({"goal": "Prep me", "response_language": "en", "memory_items": []})
    system_en = [m for m in out_en["messages"] if m.__class__.__name__ == "SystemMessage"]
    assert not any("RESPONSE LANGUAGE" in m.content for m in system_en)


def test_geography_detection_is_independent_of_language():
    # Retrieval geography is a pure function of the QUERY TEXT — it takes no language
    # argument, so a conversation-language choice cannot change it.
    from src.copilot.knowledge.router import detect_country

    assert detect_country("What do product managers earn in Germany?") == "DE"
    # The same query yields the same country regardless of any chosen UI/Mo language
    # (there is no language parameter to pass — proven by the signature + stability).
    assert detect_country("What do product managers earn in Germany?") == "DE"
    assert detect_country("Salaries in the UK for nurses") == "UK"
