"""When is an invitation required to register? (04E)

* Hosted environments (``staging``, ``production`` and ANY ``API_ENV`` value that is not a known local one, typos and unknown labels included) ALWAYS require an
  invitation. No setting can switch that off: the decision for a hosted environment never reads the override.
* Local development and tests (``development``, ``dev``, ``test``, ``testing``, ``local``) default to NOT requiring one, so the existing suites and a developer's
  first run need no codes. ``REGISTRATION_INVITATION_REQUIRED=true`` turns the requirement on there to exercise the real flow.

The environment is the SERVER's (``API_ENV`` through ``ApiSettings``), never a request field.
"""

from __future__ import annotations

import os

# The same set the rest of the API treats as local (src/api/dependencies.py DEV_ENVS); duplicated as a literal so this module imports nothing from the API layer
# (a test asserts the two stay equal).
LOCAL_ENVIRONMENTS: tuple[str, ...] = ("development", "dev", "test", "testing", "local")
OVERRIDE_ENV_VAR = "REGISTRATION_INVITATION_REQUIRED"
_TRUE = frozenset({"1", "true", "yes", "on"})

CODE_BYTES = 32                    # 256 bits of entropy
DEFAULT_TTL_DAYS = 14
MAX_TTL_DAYS = 30
MAX_OUTSTANDING_PENDING = 1000     # a bound on unredeemed codes (Admin can revoke); not a security control on its own
MAX_CODE_LENGTH = 128              # request bound only; a real code is about 43 characters


def invitation_required(env: str | None, override: str | None = None) -> bool:
    """True when registration must carry a valid invitation in ``env``.

    ``override`` is the raw value of ``REGISTRATION_INVITATION_REQUIRED`` (defaults to the process environment) and only ever matters for a LOCAL environment.
    """
    name = (env or "development").strip().lower()
    if name not in LOCAL_ENVIRONMENTS:
        return True                                                         # hosted or unknown: fail closed, not overridable
    raw = os.environ.get(OVERRIDE_ENV_VAR) if override is None else override
    return (raw or "").strip().lower() in _TRUE
