"""Static policy for governed knowledge (P10B-W10.8). Code-defined: Admin cannot change any of it."""

from __future__ import annotations

from src.copilot import constants as C
from src.copilot.knowledge.governance import SUPPORTED_LANGUAGES

# ---- authority: the repository's canonical semantics (1 = official/statistical ... 3 = reputable industry). ----
AUTHORITY_LEVELS = C.AUTHORITY_LEVELS            # (1, 2, 3): never renumbered, never extended
AUTHORITY_MEANING = {
    C.AUTHORITY_OFFICIAL: "Level 1: official or statistical source",
    C.AUTHORITY_PUBLIC_FRAMEWORK: "Level 2: public or professional framework",
    C.AUTHORITY_INDUSTRY: "Level 3: reputable public industry research",
}

# ---- languages: the 7 document/KB languages. Russian is an interface + Mo language only, NOT a KB language. ----
KB_LANGUAGES = tuple(SUPPORTED_LANGUAGES)

# ---- engineering classification of use rights. NOT legal advice and not a compliance certification. ----
LICENCE_CLASSES = ("public_official", "explicit_permissive", "internal_owned", "permission_recorded", "unclear", "restricted")
ACTIVATABLE_LICENCES = frozenset({"public_official", "explicit_permissive", "internal_owned", "permission_recorded"})
LICENCE_LABEL = {
    "public_official": "Public / official source",
    "explicit_permissive": "Explicitly permissive licence",
    "internal_owned": "Owned by Ask4Mo",
    "permission_recorded": "Permission recorded",
    "unclear": "Unclear (cannot be activated)",
    "restricted": "Restricted (cannot be activated)",
}

# ---- lifecycle ----
STATES = ("queued", "processing", "review_required", "approved", "indexing", "indexed", "active", "rejected", "failed", "retired")
# Server-side legal transitions. parsed != approved, approved != indexed, indexed != active.
TRANSITIONS = {
    "queued": {"processing", "failed"},
    "processing": {"review_required", "failed"},
    "review_required": {"approved", "rejected", "queued"},
    "approved": {"indexing", "rejected"},
    "indexing": {"indexed", "failed"},
    "indexed": {"active", "retired"},
    "active": {"retired"},
    "failed": {"queued", "indexing"},
    "rejected": set(),
    "retired": set(),
}
SCAN_STATUSES = ("not_scanned", "scan_passed", "scan_failed", "scan_unavailable")
REJECTION_REASONS = ("provenance_insufficient", "licence_not_permitted", "quality_insufficient", "out_of_scope", "unsafe_content", "duplicate", "other")
FAILED_STAGES = ("parse", "index")
INDEX_STATES = ("built", "removed", "removal_failed")

# ---- uploads: the smallest safe set (existing, tested PDF and text parsers). ----
ALLOWED_EXTENSIONS = {"pdf": "application/pdf", "txt": "text/plain", "md": "text/markdown"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
PREVIEW_CHARS = 4000
MAX_TITLE = 200
MAX_PUBLISHER = 200
MAX_PROVENANCE = 500
MAX_URL = 500

COLLECTION = "governed_knowledge"      # the ONLY collection Admin-managed knowledge is ever written to
JOB_PARSE = "knowledge_parse"
JOB_INDEX = "knowledge_index"
JOB_REMOVE = "knowledge_remove_index"
