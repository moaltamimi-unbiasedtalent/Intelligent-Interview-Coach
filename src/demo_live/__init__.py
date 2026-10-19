"""Capstone live-demonstration provider control (budget ledger, HTTP chokepoint, offline guard, kill switch).

Separate from the P10E evaluation tooling: its own ledger, its own authorization, EUR accounting, a hard cap that is never exceeded and an offline mode that never
contacts a provider even when a credential exists. See ``docs/capstone/submission/LIVE_CAPSTONE_DEMONSTRATION.md``.
"""
