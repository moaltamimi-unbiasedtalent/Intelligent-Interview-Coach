"""Speech policy for the governed server-side providers (W12.4E): the product language boundary, the code-defined authorization constants, and the VERIFIED provider capability facts.

Three things are kept separate on purpose (never derive one from another):
  * PRODUCT authorization: the seven languages the product offers speech in (``PRODUCT_SPEECH_LANGUAGES``). The interface set is larger (eight, with Russian); Russian is NOT a speech language.
  * PROVIDER capability: what a provider can do (``WHISPER_CAPABILITY`` / ``KYUTAI_CAPABILITY``). A provider claiming a language never enables it for candidates.
  * ADMIN eligibility: the subset an administrator enables (stored in ``speech_governance``); it can only narrow, never widen, the intersection.
EFFECTIVE eligibility is the intersection of all three.

Authorization is a CODE constant (the pattern of ``src.billing.policy``): no setting, Admin action, request field or environment variable can turn on a server speech provider. Configuration alone
never makes a provider operational.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["PRODUCT_SPEECH_LANGUAGES", "EXCLUDED_SPEECH_LANGUAGES", "SERVER_SPEECH_PROVIDERS_AUTHORIZED", "WHISPER_API_TRANSPORT_AUTHORIZED", "MODEL_DOWNLOADS_AUTHORIZED",
           "VOICE_CLONING_ENABLED", "STT_PROVIDER_IDS", "TTS_PROVIDER_IDS", "ProviderCapability", "WHISPER_CAPABILITY", "KYUTAI_CAPABILITY", "base_language", "effective_languages",
           "SELECTED_STT_PROVIDER", "SELECTED_TTS_PROVIDER", "GENUINE_MODEL_VALIDATION"]

# The canonical BACKEND copy of the product speech boundary. It must equal the frontend lists (``frontend/lib/speech/ttsLocales.ts`` SUPPORTED_TTS_LOCALES and the dictation languages); a test
# asserts that, so the two cannot drift. Russian stays excluded.
PRODUCT_SPEECH_LANGUAGES: tuple[str, ...] = ("en", "de", "fr", "es", "it", "pt", "nl")
EXCLUDED_SPEECH_LANGUAGES: tuple[str, ...] = ("ru",)

# --- authorization (code constants; all False in this wave) --------------------------------------------------------------------------------------------------------------------------
# Server-side speech providers may execute (transcribe or synthesize) ONLY when this is True. It is False: no provider executes.
SERVER_SPEECH_PROVIDERS_AUTHORIZED = False
# The hosted OpenAI Whisper API transport sends candidate audio to a third party. It needs its own authorization on top of the one above.
WHISPER_API_TRANSPORT_AUTHORIZED = False
# Model weights are NEVER downloaded automatically (Kyutai's are gated and licence-bound; Whisper's are large). They must be placed by an operator after a resource decision.
MODEL_DOWNLOADS_AUTHORIZED = False
# Voice cloning is not offered (Kyutai prohibits cloning without explicit lawful consent). Only built-in voices are ever used.
VOICE_CLONING_ENABLED = False
# Genuine model execution on real audio has NOT been verified (no weights, no authorization). Recorded as data for the readiness report; never inferred.
GENUINE_MODEL_VALIDATION = {"openai_whisper": "NOT_VERIFIED", "kyutai_pocket_tts": "MODEL_EXECUTION_NOT_VERIFIED"}

STT_PROVIDER_IDS = ("openai_whisper",)
TTS_PROVIDER_IDS = ("kyutai_pocket_tts",)
SELECTED_STT_PROVIDER = "openai_whisper"
SELECTED_TTS_PROVIDER = "kyutai_pocket_tts"


@dataclass(frozen=True)
class ProviderCapability:
    """Verified facts about a provider (source and verification level recorded). Not a product claim."""

    provider_id: str
    languages: tuple[str, ...]                      # product-style codes the provider is VERIFIED to support
    unverified_languages: tuple[str, ...] = ()       # claimed in one source, contradicted or unconfirmed in another: NOT eligible until verified
    notes: dict = field(default_factory=dict)


# OpenAI Whisper. Verified by reading the official ``whisper/tokenizer.py`` LANGUAGES table (100 languages; includes en, de, fr, es, it, pt, nl, and also ru and ar, which the product excludes).
# Open-weights models (MIT licence for code and weights): tiny 39M, base 74M, small 244M, medium 769M, large 1550M, turbo 809M; about 1 to 10 GB of VRAM; ffmpeg required. The hosted
# ``whisper-1`` API accepts mp3, mp4, mpeg, mpga, m4a, wav and webm up to 25 MB (secondary sources).
WHISPER_CAPABILITY = ProviderCapability(
    provider_id="openai_whisper", languages=("en", "de", "fr", "es", "it", "pt", "nl"),
    notes={"licence": "MIT (code and weights)", "models": {"tiny": "39M", "base": "74M", "small": "244M", "medium": "769M", "large": "1550M", "turbo": "809M"},
           "vram_gb": {"tiny": 1, "base": 1, "small": 2, "medium": 5, "large": 10, "turbo": 6}, "requires": ["ffmpeg"], "api_upload_limit_mb": 25,
           "verification": "language table read from the official tokenizer (100 languages); sizes and VRAM from the official README; API limits from secondary sources",
           "deployments": ["self_hosted (open weights, audio stays on our infrastructure)", "hosted_api (audio goes to a third party; separately authorized)"]})

# Kyutai Pocket TTS. The official GitHub README lists english, french, german, portuguese, italian, spanish and dutch; the official Hugging Face model card lists six (no Dutch). The two official
# pages DISAGREE about Dutch, so Dutch is UNVERIFIED and not eligible. Roughly 100M parameters, CPU capable (about 6x real time on a laptop-class CPU, per the README), Python 3.10 to 3.14
# with PyTorch 2.5+, package ``pocket-tts``; code MIT; weights cc-by-4.0 and GATED (access requires sharing contact information); the per-voice licences are on a separate page that was not
# verified; voice cloning without explicit lawful consent is prohibited.
KYUTAI_CAPABILITY = ProviderCapability(
    provider_id="kyutai_pocket_tts", languages=("en", "fr", "de", "pt", "it", "es"), unverified_languages=("nl",),
    notes={"licence": "code MIT; weights cc-by-4.0 (gated); per-voice licences NOT VERIFIED", "parameters": "about 100M", "requires": ["pocket-tts", "torch>=2.5", "python 3.10-3.14"],
           "cpu": "CPU capable; about 2 cores", "builtin_voices": {"en": "alba", "fr": "estelle", "de": "juergen", "it": "giovanni", "pt": "rafael", "es": "lola"},
           "model_names": {"en": "english", "fr": "french", "de": "german", "pt": "portuguese", "it": "italian", "es": "spanish"},
           "verification": "official GitHub README and Hugging Face model card read; they disagree about Dutch (README yes, card no): Dutch is unverified", "prohibited_use": "voice cloning without explicit lawful consent"})


def base_language(code: str | None) -> str | None:
    """``de-DE`` -> ``de``; anything that is not a plain language tag -> ``None``. Never maps a language to a country."""
    if not code or not isinstance(code, str):
        return None
    base = code.strip().lower().replace("_", "-").split("-", 1)[0]
    return base if base.isalpha() and 2 <= len(base) <= 3 else None


def effective_languages(capability: ProviderCapability, admin_enabled: tuple[str, ...] | list[str] | None = None) -> tuple[str, ...]:
    """PRODUCT boundary AND provider capability AND the administrator's selection (which can only narrow). Russian and every unsupported language is always excluded."""
    product = set(PRODUCT_SPEECH_LANGUAGES) - set(EXCLUDED_SPEECH_LANGUAGES)
    allowed = product & set(capability.languages)
    if admin_enabled is not None:
        allowed &= set(admin_enabled)
    return tuple(c for c in PRODUCT_SPEECH_LANGUAGES if c in allowed)
