# Restore drill record: drill-20261022T122512Z-offline-sealed

- Result: **PASS**
- Kind: `offline_synthetic` (synthetic offline environment, NOT the hosted staging environment)
- Hosted verification: **NOT RUN (OD-HOSTED)**
- Started: 2026-10-22T12:25:12.317629+00:00  Finished: 2026-10-22T12:25:12.432370+00:00
- Commit: `092f99b3`  Tool: `ask4mo-backup-set/1`
- Database dialect: `sqlite`; restored into a separate environment: True

## Backup set

- Set id `e604f829d92446acb105f5ca64103928`, created 2026-10-22T12:25:12.322389+00:00, encryption `aes-256-gcm-chunked`, manifest signed: True, consistent: True
- Manifest SHA-256 `8c1b44da1e9aba99033f0ffb89350cd62ddc239e7ad1c8a487ec3a8d1437b2bd` (record this out of band: it anchors an unsigned manifest)
- 16 files, 93 tables, 36 rows, 4 private documents, 4 index chunks (index checksum prefix `62d1a647c3cfe195`), schema revision `0043_story_bank_completion`

## Checks

| Check | Result | Detail |
|---|---|---|
| One consistent backup set of database, documents and knowledge was created | PASS | codes=[], counts={'tables': 93, 'rows': 36, 'document_files': 4, 'symlinks_skipped': 0, 'files': 16, 'chunks': 4}, consistent=True |
| Every file checksum (stored and plaintext) and the manifest signature verify | PASS | codes=[], counts={'files_checked': 16, 'files_missing': 0, 'files_modified': 0, 'files_unlisted': 0, 'paths_unsafe': 0} |
| A restore without --execute plans and writes nothing | PASS | codes=[] |
| The set was restored into a SEPARATE environment | PASS | codes=[] |
| A second restore into the same (now non-empty) target is refused | PASS | codes=['target_not_empty'] |
| The restored schema revision equals the manifest's | PASS | revision=0043_story_bank_completion, manifest_revision=0043_story_bank_completion |
| Every table's restored row count equals the manifest | PASS | tables_checked=93, rows=36, tables_different=[] |
| Every restored private document equals its manifest checksum | PASS | files_checked=4, files_different=0 |
| Every restored governed-knowledge source file equals its manifest checksum | PASS | files_checked=2, files_different=0 |
| The restored index collection checksum equals the manifest's and the live source's | PASS | chunks=4, checksum_prefix=62d1a647c3cfe195, compared_with_live_source=True |
| Re-running the recorded retrieval probes on the restored index gives the same chunks and scores | PASS | queries=4, top_k=3, queries_different=0, embedder=local_hash |
| A modified document file is detected by verification | PASS | codes=['file_checksum_mismatch'] |
| A restore of a tampered set is refused and writes nothing | PASS | codes=['backup_integrity_failed', 'file_checksum_mismatch'] |
| A file added to the set but not listed in the manifest is detected | PASS | codes=['unlisted_file'] |
| An edited manifest is detected by the manifest signature | PASS | codes=['manifest_tampered'] |
| The drill only read the source: tables, document files, knowledge files and index are unchanged | PASS | - |

## Not exercised

- hosted staging backup and restore (OD-HOSTED)
- PostgreSQL pg_dump and pg_restore through this harness unless dialect is postgresql
- restore time and size at real data volume
- off-site or object-storage copy of the set

## Timings

- backup_seconds: 0.038
- restore_seconds: 0.019

This record contains counts, short hashes and fixed codes only. It carries no path, key, URL or candidate data.
