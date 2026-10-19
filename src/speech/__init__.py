"""Governed server-side speech providers (W12.4E): Whisper speech-to-text and Kyutai Pocket TTS adapters, the language boundary, audio lifecycle, readiness and Admin governance.

Reuses the existing provider-agnostic ``src/speech_service.py`` interface and types; it does not replace the browser speech paths (P3 dictation, P7 speech output) or the realtime voice
capability (P7.5, a separate capability). Nothing here contacts a provider unless the code constants in ``src.speech.policy`` authorise it (they do not).
"""
