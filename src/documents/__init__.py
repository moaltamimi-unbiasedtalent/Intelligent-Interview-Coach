"""Private candidate documents & evidence (Capstone P4/E2/E3).

Owner-scoped upload → validate → private store → parse/OCR → deterministic structured
extraction → user review → approved evidence → story bank → export/delete.

Security posture: uploaded documents are **untrusted DATA**, never instructions. In P4
no document text is ever placed into an LLM prompt (extraction is deterministic; stories
are user-/deterministically-built), so document content cannot influence Mo, tools or
retrieval. Files are stored privately (never a public URL), owner-scoped, and removed on
deletion. Nothing becomes public knowledge or approved memory automatically.
"""

from __future__ import annotations

__all__: list[str] = []
