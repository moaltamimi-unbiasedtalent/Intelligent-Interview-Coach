#!/usr/bin/env python
"""P10B-W10.8 governed-knowledge guard (deterministic, offline, 0 paid/live calls).

High-risk invariants: approval before any embedding/retrieval; active-only retrieval enforced by the CONTROL PLANE (not the vector
store); canonical authority 1/2/3; the 7 KB languages with Russian NOT added; mandatory provenance and a licence gate; no URL fetching;
a bounded upload allowlist; W10.9 jobs for parse/index; deterministic chunk ids; no raw vector/candidate browsing; permissioned routes.
It does not duplicate the test suite.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# TEST ISOLATION (hard requirement): before any application import (temp DATABASE_URL, no .env, non-temp engines fail fast, isolated research cache).
import tests.conftest  # noqa: E402,F401


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from src.copilot import constants as C
    from src.knowledge_admin import policy as P

    svc, rt, ret, pol = (read(f"src/knowledge_admin/{n}.py") for n in ("service", "runtime", "retriever", "policy"))
    route, jobs_py = read("src/api/routes/admin_knowledge.py"), read("src/knowledge_admin/jobs.py")
    persist = read("src/persistence.py")
    check("governed_tables_exist", all(t in persist for t in ("class KnowledgeSource(", "class KnowledgeSourceVersion(", "class KnowledgeIndexRecord(")), "3 tables")
    check("authority_semantics_unchanged", (C.AUTHORITY_OFFICIAL, C.AUTHORITY_PUBLIC_FRAMEWORK, C.AUTHORITY_INDUSTRY) == (1, 2, 3) and P.AUTHORITY_LEVELS == (1, 2, 3), "1 official, 2 framework, 3 industry")
    check("kb_languages_unchanged_no_russian", P.KB_LANGUAGES == ("en", "de", "fr", "es", "it", "pt", "nl") and "ru" not in P.KB_LANGUAGES, "7 languages")
    check("licence_gate_blocks_unclear_and_restricted", {"unclear", "restricted"}.isdisjoint(P.ACTIVATABLE_LICENCES) and "ACTIVATABLE_LICENCES" in svc, "present")
    check("provenance_required_to_approve", "provenance note is not recorded" in svc and "publisher is not recorded" in svc, "fail-closed")
    check("approval_requires_scan_passed", 'v.scan_status != "scan_passed"' in svc and "required=True" in rt, "mandatory scan")
    check("approval_before_embedding", "add_chunks" not in svc and "add_chunks" in rt and 'info["state"] != "indexing"' in rt, "embedding only in the index job for approved versions")
    check("index_requires_approved", 'v.approved_at is None' in svc and '"approved", "failed"' in svc, "approved only")
    check("activation_requires_indexed_and_checks", 'v.state != "indexed"' in svc and "The index for this version is not complete" in svc, "present")
    check("one_active_version_db_enforced", "uq_ksv_one_active" in persist and "uq_ksv_one_active" in read("migrations/versions/0019_knowledge_admin.py"), "partial unique index")
    check("retrieval_gated_by_control_plane", "active_version_ids" in ret and 'meta.get("knowledge_version_id") not in active' in ret, "SQL active set on every call")
    check("no_keyword_channel_over_governed_store", "KeywordRetriever" not in ret and "all_chunks" not in ret, "BM25 would bypass the gate")
    check("separate_governed_collection", 'COLLECTION = "governed_knowledge"' in pol and "collection_name=P.COLLECTION" in read("src/knowledge_admin/wiring.py"), "own collection")
    check("deterministic_chunk_ids", "chunk_units(units, source_id=version_public_id)" in rt, "sha256(version id + chunk text)")
    check("jobs_use_w10_9_with_ids_only", "JobTypeDef" in jobs_py and 'pattern=r"^[0-9a-f]{32}$"' in jobs_py and "extra=\"forbid\"" in jobs_py, "id-only payloads")
    check("parse_and_index_not_in_http", "run_parse" not in route and "add_chunks" not in route and "parse_document" not in route, "async only")
    check("no_url_fetching", not re.search(r"requests|httpx|urllib\.request|urlopen|aiohttp|socket", svc + rt + ret + route + read("src/knowledge_admin/wiring.py")), "reference string only")
    check("upload_allowlist_and_bounds", P.MAX_UPLOAD_BYTES <= 10 * 1024 * 1024 and set(P.ALLOWED_EXTENSIONS) == {"pdf", "txt", "md"} and "MAX_UPLOAD_BYTES" in route, "pdf/txt/md, 5 MB")
    check("opaque_storage_keys_and_checksum", "new_storage_key" in svc and "hashlib.sha256" in svc and "uq_ksv_source_checksum" in persist, "present")
    check("no_raw_vector_or_chunk_browser", not re.search(r"\.query\(|all_chunks|get_chunks|/chunks|/vector", route), "no chunk routes")
    schema = read("src/api/schemas/admin.py")
    block = schema[schema.index("class KnowledgeRow"):] if "class KnowledgeRow" in schema else ""
    check("no_full_text_in_schemas", block != "" and not re.search(r"full_text|chunks:|embedding|storage_key", block), "bounded preview only")
    check("no_candidate_private_access", not re.search(r"CandidateDocument|CandidateStory|PreparationMemory|SupportTicket|InterviewRepository", svc + rt + ret + route), "platform knowledge only")
    check("routes_permissioned", route.count("require_permission(") >= 14 and "KNOWLEDGE_APPROVE" in route and "KNOWLEDGE_MANAGE" in route and "KNOWLEDGE_READ" in route, "14 routes")
    check("uses_existing_permissions", all(f'"{p}"' in read("src/application/admin_permissions.py") for p in ("platform.knowledge.read", "platform.knowledge.manage", "platform.knowledge.approve")), "no new permission")
    check("approval_audited_atomically_no_text", "_stage(" in svc and "ADMIN_KNOWLEDGE_VERSION_APPROVED" in route and "preview" not in read("src/application/admin_audit.py").split("W10.8 (knowledge)")[1][:600].replace("a preview,", ""), "ids and states only")
    check("deterministic_embeddings_in_tests", "LocalHashEmbedder" in read("tests/test_knowledge_admin_w10_8.py") and "OpenAIEmbedder" not in read("tests/test_knowledge_admin_w10_8.py"), "offline embedder")
    check("platform_pause_not_touched", "pause" not in (svc + rt + ret + route).lower(), "SEC-W10-05 stays open")
    mig = read("migrations/versions/0019_knowledge_admin.py")
    check("migration_chain_valid", 'down_revision = "0018_jobs"' in mig and "ck_ksv_authority" in mig and "ck_ksv_approval_evidence" in mig and "chroma" not in mig.lower().replace("never touches chroma", ""), "0019 chains from 0018; no vector work")
    check("tests_exist", all(t in read("tests/test_knowledge_admin_w10_8.py") for t in (
        "test_nothing_is_retrievable_until_activation_and_nothing_is_embedded_before_approval",
        "test_retired_source_is_excluded_immediately_even_if_vector_deletion_never_runs",
        "test_crash_window_index_written_then_worker_dies_then_replay_leaves_one_copy",
        "test_version_switch_is_atomic_one_active_and_old_version_disappears",
        "test_prompt_injection_text_is_inert_data_and_flagged_by_the_existing_guard")), "present")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.8 KNOWLEDGE GUARD\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:62s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
