"""Voice services (Capstone P7.5).

Realtime voice session minting and its provider-neutral seam. This package holds NO
audio: the browser streams audio directly to the realtime provider over WebRTC, and the
backend only mints short-lived, user-scoped session credentials. No microphone audio or
transcript ever passes through or is stored by this package.
"""
