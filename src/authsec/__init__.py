"""Authentication security primitives for the identity foundation (Capstone P1/E1).

Named ``authsec`` to avoid colliding with the pre-existing prompt-injection
:mod:`src.security` module. Small, dependency-light, unit-testable helpers used by
the authentication and authorization layers:

* :mod:`src.authsec.passwords` — modern password hashing (bcrypt).
* :mod:`src.authsec.tokens` — opaque, high-entropy tokens and their at-rest hash.

These modules make **no** provider/network call and hold **no** secret material;
they never log or print a password, token or hash.
"""

from __future__ import annotations

__all__: list[str] = []
