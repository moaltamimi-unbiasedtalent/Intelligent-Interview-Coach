"""Worker-side billing runtime holder (P10B-W10.5). Kept free of job-registry imports to avoid an import cycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BillingRuntime:
    session_factory: Any
    provider: Any = None          # the MOCK adapter when billing is enabled, else None
    mode: Any = None
    jobs: Any = None
