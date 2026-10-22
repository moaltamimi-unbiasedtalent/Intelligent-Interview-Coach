"""Invitation-only private beta registration (package 04E, REQ-BETA-01).

``policy`` decides WHEN an invitation is required (fail-closed in every hosted environment), ``repository`` owns the hashed single-use invitation rows and the atomic
redemption statement, ``service`` is the Admin issue/list/revoke orchestration. Nothing here sends email or calls a provider.
"""
