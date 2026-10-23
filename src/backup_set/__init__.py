"""Backup sets, restore drills, backup erasure and rollback rehearsal (package 05B, PG-09).

One operator-facing tool family (no API route, no candidate surface, no provider call):

* ``engine``   - ONE consistent, checksummed, manifest-described backup set of the database, the private candidate documents and the governed knowledge
                 (registry, private files, index) with a dry-run default, refusals instead of overwrites, tamper detection and optional AES-256-GCM sealing.
* ``erasure``  - the backup-erasure procedure that follows an account deletion (PRIV-BACKUP): an append-only ledger, a plan, a rewrite of a set and operator
                 attestations. It never claims erasure from a backup that was not rewritten or destroyed.
* ``drill``    - the restore drill harness that restores into a SEPARATE environment, verifies it and writes a JSON and markdown drill record.
* ``rollback`` - the migration rollback rehearsal (upgrade, fail-closed downgrade, clean downgrade, re-upgrade) on an isolated SQLite database.

Reports and manifests carry fixed codes, kinds, counts and short hashes. They never carry a key, a URL, a credential or an absolute path.
"""
