"""Restore drill harness (package 05B, PG-09, EX-12.7/12.8).

A drill takes a backup set of a SOURCE environment, restores it into a SEPARATE environment, verifies the restored environment against the set manifest and
against the live source, runs the negative checks (a restore refuses a non-empty target, a tampered set is detected) and writes a drill RECORD (JSON and
markdown). The source is only read; the record never contains a path, a key, a URL or candidate data.

WHAT A PASS MEANS. PASS = every check below passed in the environment named in the record (``kind``). A drill on the SYNTHETIC offline environment proves the tool
and the procedure; it is NOT evidence about the hosted staging environment, and every record states ``hosted_verification: NOT RUN (OD-HOSTED)`` until a drill is
run there by the operator with ``kind: operator_supplied``.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.backup_set import engine as E
from src.knowledge_admin import policy as KP
from src.knowledge_admin.recovery import collection_checksum

RECORD_FORMAT = 1
HOSTED_STATUS = "NOT RUN (OD-HOSTED)"
_LABEL = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_SHA = re.compile(r"^[0-9a-f]{7,64}$")
# Safety net for the record itself: nothing that looks like a path or a URL may be written into it.
_UNSAFE = re.compile(r"(/Users/|/Volumes/|/private/|/tmp/|/var/|/home/|[A-Za-z]:\\|://)")


@dataclass
class Check:
    id: str
    title: str
    result: str                         # PASS | FAIL | NOT_RUN
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "result": self.result, "detail": self.detail}


@dataclass
class DrillResult:
    record: dict
    json_name: str | None = None
    md_name: str | None = None

    @property
    def overall(self) -> str:
        return self.record["overall"]


def _open_store(index_dir: Path):
    from src.copilot.embeddings import LocalHashEmbedder
    from src.copilot.vectorstore import ChromaStore

    return ChromaStore(LocalHashEmbedder(), persist_dir=str(index_dir), collection_name=KP.COLLECTION)


def _source_fingerprint(source: E.Source) -> dict:
    return {"tables": E.table_counts(source.database_url), "documents": E._tree_fingerprint(Path(source.documents_dir)),
            "knowledge_files": E._tree_fingerprint(Path(source.knowledge_files_dir) if source.knowledge_files_dir else None),
            "index": E._tree_fingerprint(Path(source.knowledge_index_dir) if source.knowledge_index_dir else None, mtimes=False)}


def _tamper_checks(set_dir: Path, work: Path, manifest: dict, encryption_key: bytes | None, signing_key: bytes | None) -> list[Check]:
    out = []
    docs = sorted(k for k in manifest["files"] if k.startswith(E.DOCS_DIR + "/"))
    signed = bool(manifest.get("signature"))
    # (a) flip one byte of a stored document
    if docs:
        c = work / "tamper-a"
        shutil.copytree(set_dir, c)
        victim = c / manifest["files"][docs[0]]["stored"]
        data = bytearray(victim.read_bytes())
        data[len(data) // 2] ^= 0x01
        victim.write_bytes(bytes(data))
        r = E.verify_set(c, encryption_key=encryption_key, signing_key=signing_key)
        out.append(Check("tamper_file_detected", "A modified document file is detected by verification", "PASS" if (not r.ok and "file_checksum_mismatch" in r.codes) else "FAIL",
                         {"codes": [x for x in r.codes if x.startswith("file_") or x.startswith("sealed_")]}))
        rr = E.restore_set(c, target_root=work / "tamper-a-restore", execute=True, encryption_key=encryption_key, signing_key=signing_key)
        out.append(Check("tamper_restore_refused", "A restore of a tampered set is refused and writes nothing", "PASS" if (not rr.ok and "backup_integrity_failed" in rr.codes
                                                                                                                    and not (work / "tamper-a-restore").exists()) else "FAIL",
                         {"codes": rr.codes[:3]}))
    # (b) an unlisted file
    c = work / "tamper-b"
    shutil.copytree(set_dir, c)
    (c / "documents").mkdir(exist_ok=True)
    (c / "documents" / "injected-file").write_bytes(b"not in the manifest")
    r = E.verify_set(c, encryption_key=encryption_key, signing_key=signing_key)
    out.append(Check("tamper_unlisted_file_detected", "A file added to the set but not listed in the manifest is detected", "PASS" if "unlisted_file" in r.codes else "FAIL", {"codes": r.codes[:3]}))
    # (c) an edited manifest (row counts rewritten to hide a deletion)
    c = work / "tamper-c"
    shutil.copytree(set_dir, c)
    mp = c / E.MANIFEST
    m = json.loads(mp.read_text(encoding="utf-8"))
    first = sorted(m["database"]["row_counts"])[0]
    m["database"]["row_counts"][first] += 1
    mp.write_text(json.dumps(m, sort_keys=True, indent=1), encoding="utf-8")
    r = E.verify_set(c, encryption_key=encryption_key, signing_key=signing_key, require_signature=True)
    if signed:
        out.append(Check("tamper_manifest_detected", "An edited manifest is detected by the manifest signature", "PASS" if "manifest_tampered" in r.codes else "FAIL", {"codes": r.codes[:3]}))
    else:
        out.append(Check("tamper_manifest_detected", "An edited manifest is detected by the manifest signature", "NOT_RUN",
                         {"reason": "set_not_signed: without a signing key the manifest is protected only by an out-of-band record of its SHA-256", "require_signature_refuses": "manifest_unsigned" in r.codes}))
    return out


def run_drill(source: E.Source, *, work_dir: str | Path, record_dir: str | Path | None, label: str = "drill", kind: str = "offline_synthetic",
              encryption_key: bytes | None = None, signing_key: bytes | None = None, storage_encrypted_attested: bool = False, api_env: str | None = "test",
              commit_sha: str | None = None, negative_checks: bool = True, target_database_url: str | None = None,
              clock: Callable[[], datetime] | None = None) -> DrillResult:
    """``target_database_url`` is only for a PostgreSQL source: an EMPTY disposable database whose name contains restore, staging or drill (never printed)."""
    if not _LABEL.match(label):
        raise ValueError("invalid drill label")
    if kind not in ("offline_synthetic", "operator_supplied"):
        raise ValueError("invalid drill kind")
    if commit_sha is not None and not _SHA.match(commit_sha):
        raise ValueError("invalid commit sha")
    now = (clock or (lambda: datetime.now(timezone.utc)))
    started = now()
    work = Path(work_dir)
    if work.exists() and any(work.iterdir()):
        raise ValueError("drill work directory must be new or empty")
    work.mkdir(parents=True, exist_ok=True)
    checks: list[Check] = []
    timings: dict[str, float] = {}
    set_dir, target = work / "set", work / "restored"
    before = _source_fingerprint(source)

    t0 = time.monotonic()
    created = E.create_set(source, out_dir=set_dir, execute=True, encryption_key=encryption_key, signing_key=signing_key,
                           storage_encrypted_attested=storage_encrypted_attested, api_env=api_env, clock=clock)
    timings["backup_seconds"] = round(time.monotonic() - t0, 3)
    checks.append(Check("backup_set_created", "One consistent backup set of database, documents and knowledge was created", "PASS" if created.ok else "FAIL",
                        {"codes": created.codes, "counts": created.counts, "consistent": created.details.get("consistent")}))
    manifest: dict[str, Any] = {}
    if created.ok:
        manifest = E.load_manifest(set_dir)
        v = E.verify_set(set_dir, encryption_key=encryption_key, signing_key=signing_key)
        checks.append(Check("set_verified", "Every file checksum (stored and plaintext) and the manifest signature verify", "PASS" if v.ok else "FAIL", {"codes": v.codes, "counts": v.counts}))
        dry = E.restore_set(set_dir, target_root=target, execute=False, encryption_key=encryption_key, signing_key=signing_key, target_database_url=target_database_url)
        checks.append(Check("restore_dry_run_writes_nothing", "A restore without --execute plans and writes nothing", "PASS" if (dry.ok and not target.exists()) else "FAIL",
                            {"codes": dry.codes}))
        t0 = time.monotonic()
        restored = E.restore_set(set_dir, target_root=target, execute=True, encryption_key=encryption_key, signing_key=signing_key, target_database_url=target_database_url)
        timings["restore_seconds"] = round(time.monotonic() - t0, 3)
        checks.append(Check("restore_executed", "The set was restored into a SEPARATE environment", "PASS" if restored.ok else "FAIL", {"codes": restored.codes}))
        if restored.ok:
            lay = E.restore_layout(target)
            db_url = f"sqlite:///{lay['database']}" if manifest["database"]["dialect"] == "sqlite" else target_database_url
            again = E.restore_set(set_dir, target_root=target, execute=True, encryption_key=encryption_key, signing_key=signing_key, target_database_url=target_database_url)
            checks.append(Check("restore_refuses_non_empty_target", "A second restore into the same (now non-empty) target is refused", "PASS" if (not again.ok and "target_not_empty" in again.codes) else "FAIL",
                                {"codes": again.codes[:2]}))
            if db_url:
                rev = E.schema_revision(db_url)
                checks.append(Check("schema_revision_matches", "The restored schema revision equals the manifest's", "PASS" if rev == manifest["database"]["schema_revision"] else "FAIL",
                                    {"revision": rev, "manifest_revision": manifest["database"]["schema_revision"]}))
                diff = E.row_count_diff(manifest, db_url)
                checks.append(Check("row_counts_match", "Every table's restored row count equals the manifest", "PASS" if not diff else "FAIL",
                                    {"tables_checked": manifest["database"]["tables"], "rows": sum(manifest["database"]["row_counts"].values()), "tables_different": sorted(diff)[:20]}))
            bad = [k for k, e in manifest["files"].items() if k.startswith(E.DOCS_DIR + "/") and (not (target / k).is_file() or E.sha_file(target / k) != e["sha256"])]
            checks.append(Check("document_checksums_match", "Every restored private document equals its manifest checksum", "PASS" if not bad else "FAIL",
                                {"files_checked": manifest["documents"]["count"], "files_different": len(bad)}))
            kfiles_bad = 0
            kcount = 0
            for k, e in manifest["files"].items():
                if k.startswith(E.KNOWLEDGE_DIR + "/files/"):
                    kcount += 1
                    p = lay["knowledge_files"] / k[len(E.KNOWLEDGE_DIR + "/files/"):]
                    if not p.is_file() or E.sha_file(p) != e["sha256"]:
                        kfiles_bad += 1
            checks.append(Check("knowledge_files_match", "Every restored governed-knowledge source file equals its manifest checksum", "PASS" if not kfiles_bad else "FAIL",
                                {"files_checked": kcount, "files_different": kfiles_bad}))
            want = manifest["knowledge"]["index_checksum"]
            if lay["knowledge_index"].is_dir():
                rs = _open_store(lay["knowledge_index"])
                got = collection_checksum(rs.all_chunks())
                live = None
                if source.knowledge_index_dir and Path(source.knowledge_index_dir).is_dir():
                    live = collection_checksum(_open_store(Path(source.knowledge_index_dir)).all_chunks())
                ok = want is not None and got == want and (live is None or live == want)
                checks.append(Check("index_checksum_matches", "The restored index collection checksum equals the manifest's and the live source's", "PASS" if ok else "FAIL",
                                    {"chunks": manifest["knowledge"]["chunks"], "checksum_prefix": (got or "")[:16], "compared_with_live_source": live is not None}))
                probe = manifest.get("retrieval_probe") or {}
                if probe.get("run"):
                    mismatches = 0
                    for q in probe["queries"]:
                        hits = rs.query(q["query"], top_k=probe["top_k"])
                        if [h.chunk_id for h in hits] != q["hit_ids"] or [round(float(h.score), 6) for h in hits] != q["scores"]:
                            mismatches += 1
                    checks.append(Check("retrieval_parity", "Re-running the recorded retrieval probes on the restored index gives the same chunks and scores", "PASS" if not mismatches else "FAIL",
                                        {"queries": len(probe["queries"]), "top_k": probe["top_k"], "queries_different": mismatches, "embedder": probe.get("embedder")}))
                else:
                    checks.append(Check("retrieval_parity", "Re-running the recorded retrieval probes on the restored index gives the same chunks and scores", "NOT_RUN",
                                        {"reason": probe.get("reason", "probe_not_recorded")}))
            else:
                checks.append(Check("index_checksum_matches", "The restored index collection checksum equals the manifest's", "NOT_RUN", {"reason": "source_has_no_index"}))
                checks.append(Check("retrieval_parity", "Retrieval evidence parity", "NOT_RUN", {"reason": "source_has_no_index"}))
        if negative_checks:
            checks.extend(_tamper_checks(set_dir, work, manifest, encryption_key, signing_key))
    after = _source_fingerprint(source)
    checks.append(Check("source_unchanged", "The drill only read the source: tables, document files, knowledge files and index are unchanged", "PASS" if before == after else "FAIL", {}))

    finished = now()
    results = [c.result for c in checks]
    overall = "FAIL" if "FAIL" in results else ("PARTIAL" if "NOT_RUN" in results else "PASS")
    s = manifest or {}
    record = {
        "record_format": RECORD_FORMAT, "drill_id": f"drill-{started.strftime('%Y%m%dT%H%M%SZ')}-{label}", "label": label, "kind": kind,
        "started_at": started.isoformat(), "finished_at": finished.isoformat(), "durations": timings, "commit_sha": commit_sha, "tool": E.TOOL,
        "environment": {"dialect": source.dialect(), "separate_target_environment": True, "hosted": False, "api_env": api_env},
        "hosted_verification": HOSTED_STATUS,
        "set": {"set_id": s.get("set_id"), "created_at": s.get("created_at"), "encryption": (s.get("encryption") or {}).get("mode"), "signed": bool(s.get("signature")),
                "manifest_sha256": created.details.get("manifest_sha256"), "files": len(s.get("files", {})), "tables": (s.get("database") or {}).get("tables"),
                "rows": sum(((s.get("database") or {}).get("row_counts") or {}).values()), "document_files": (s.get("documents") or {}).get("count"),
                "chunks": (s.get("knowledge") or {}).get("chunks"), "index_checksum_prefix": ((s.get("knowledge") or {}).get("index_checksum") or "")[:16] or None,
                "schema_revision": (s.get("database") or {}).get("schema_revision"), "consistent": (s.get("consistency") or {}).get("consistent")},
        "checks": [c.to_dict() for c in checks], "overall": overall,
        "not_exercised": ["hosted staging backup and restore (OD-HOSTED)", "PostgreSQL pg_dump and pg_restore through this harness unless dialect is postgresql",
                          "restore time and size at real data volume", "off-site or object-storage copy of the set"] if kind == "offline_synthetic" else
                         ["anything not listed in checks"],
    }
    blob = json.dumps(record)
    if _UNSAFE.search(blob):
        raise RuntimeError("drill record contains a path-like or URL-like string")      # a bug in this harness, never written
    result = DrillResult(record)
    if record_dir is not None:
        rd = Path(record_dir)
        rd.mkdir(parents=True, exist_ok=True)
        stem = record["drill_id"]
        for suffix in ("json", "md"):
            if (rd / f"{stem}.{suffix}").exists():
                raise FileExistsError("drill record already exists")                    # never overwrite a record
        (rd / f"{stem}.json").write_text(json.dumps(record, sort_keys=True, indent=1) + "\n", encoding="utf-8")
        (rd / f"{stem}.md").write_text(render_markdown(record), encoding="utf-8")
        result.json_name, result.md_name = f"{stem}.json", f"{stem}.md"
    return result


def render_markdown(r: dict) -> str:
    s = r["set"]
    lines = [f"# Restore drill record: {r['drill_id']}", "",
             f"- Result: **{r['overall']}**", f"- Kind: `{r['kind']}`" + (" (synthetic offline environment, NOT the hosted staging environment)" if r["kind"] == "offline_synthetic" else ""),
             f"- Hosted verification: **{r['hosted_verification']}**", f"- Started: {r['started_at']}  Finished: {r['finished_at']}",
             f"- Commit: `{r['commit_sha'] or 'not recorded'}`  Tool: `{r['tool']}`",
             f"- Database dialect: `{r['environment']['dialect']}`; restored into a separate environment: {r['environment']['separate_target_environment']}", "",
             "## Backup set", "",
             f"- Set id `{s['set_id']}`, created {s['created_at']}, encryption `{s['encryption']}`, manifest signed: {s['signed']}, consistent: {s['consistent']}",
             f"- Manifest SHA-256 `{s['manifest_sha256']}` (record this out of band: it anchors an unsigned manifest)",
             f"- {s['files']} files, {s['tables']} tables, {s['rows']} rows, {s['document_files']} private documents, {s['chunks']} index chunks "
             f"(index checksum prefix `{s['index_checksum_prefix']}`), schema revision `{s['schema_revision']}`", "",
             "## Checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    for c in r["checks"]:
        detail = ", ".join(f"{k}={v}" for k, v in c["detail"].items()) or "-"
        lines.append(f"| {c['title']} | {c['result']} | {detail} |")
    lines += ["", "## Not exercised", ""] + [f"- {x}" for x in r["not_exercised"]]
    lines += ["", "## Timings", ""] + [f"- {k}: {v}" for k, v in r["durations"].items()]
    lines += ["", "This record contains counts, short hashes and fixed codes only. It carries no path, key, URL or candidate data.", ""]
    return "\n".join(lines)
