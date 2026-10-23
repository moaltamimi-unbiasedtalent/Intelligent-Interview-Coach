"""A SYNTHETIC environment for restore drills and tests (package 05B). Nothing here is real candidate data: fixed placeholder names, generated text, a local hashing
embedder, a file SQLite database under the directory you give it. It is only ever built under a directory the caller creates (a temp directory in tests and in the
committed drill), never over a development or hosted store.

Layout under ``root`` (which is also the data root, ``COPILOT_DATA_DIR``): ``app.db``, ``documents/`` (private candidate files), ``knowledge_private/`` (governed source
files) and ``chroma/`` (the persistent governed index), the same defaults the API and the worker resolve.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from src.backup_set.engine import Source
from src.knowledge_admin import policy as KP

KNOWLEDGE_TEXTS = (
    ("Prioritisation frameworks help product managers rank a roadmap using customer evidence and measured adoption.",
     "Discovery interviews reveal customer problems before a team commits engineering effort to a solution."),
    ("Negotiation preparation covers a clear walk-away point, a documented market range and the order of concessions.",
     "A structured answer states the situation, the action taken and the measurable result in plain language."),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_synthetic_environment(root: Path, *, users: int = 2, documents_per_user: int = 2, use_alembic: bool = False) -> Source:
    """Create the synthetic source under the NEW directory ``root`` and return its ``Source``. Refuses an existing, non-empty ``root``. ``use_alembic`` builds the schema with the
    real migration chain (so the set records a real schema revision) instead of ``init_db``; slower, used by the committed drill."""
    from src.copilot.embeddings import LocalHashEmbedder
    from src.copilot.models import DocumentChunk
    from src.copilot.vectorstore import ChromaStore
    from src.persistence import (CandidateDocument, DocumentVersion, KnowledgeIndexRecord, KnowledgeSource, KnowledgeSourceVersion, User, init_db, make_engine,
                                 make_session_factory)

    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError("synthetic environment root must be new or empty")
    docs, kfiles, kindex = root / "documents", root / "knowledge_private", root / "chroma"
    for d in (docs, kfiles):
        d.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{root / 'app.db'}"
    if use_alembic:
        from src.backup_set.rollback import _alembic

        if _alembic(url, "upgrade", "head")[0] != 0:
            raise RuntimeError("alembic upgrade failed")
        engine = make_engine(url)
    else:
        engine = make_engine(url)
        init_db(engine)
    sf = make_session_factory(engine)
    now = datetime(2026, 10, 22, 8, 0, tzinfo=timezone.utc)
    with sf() as s:
        ids = []
        for n in range(1, users + 1):
            u = User(subject=f"synthetic-user-{n}", provider="synthetic", email=f"synthetic{n}@example.invalid")
            s.add(u)
            s.flush()
            ids.append(u.id)
            for d in range(documents_per_user):
                doc = CandidateDocument(user_id=u.id, title=f"Synthetic document {n}-{d}", category="other")
                s.add(doc)
                s.flush()
                key = hashlib.sha256(f"synthetic-doc-{n}-{d}".encode()).hexdigest()[:48]
                data = f"Synthetic private document {n}-{d}. Placeholder text only; not a real candidate record.\n".encode() * (3 + d)
                (docs / key).write_bytes(data)
                s.add(DocumentVersion(document_id=doc.id, version=1, original_filename=f"synthetic-{n}-{d}.txt", storage_key=key, mime_type="text/plain", size_bytes=len(data)))
        admin = User(subject="synthetic-admin", provider="synthetic", email="synthetic-admin@example.invalid", platform_role="platform_admin")   # approves knowledge; never a deletion subject
        s.add(admin)
        s.flush()
        approver = admin.id
        chunks = []
        for i, texts in enumerate(KNOWLEDGE_TEXTS, start=1):
            ks = KnowledgeSource(public_id=f"ks{i:030d}", title=f"Synthetic framework {i}", created_by_user_id=approver)
            s.add(ks)
            s.flush()
            body = "\n\n".join(texts).encode()
            skey = hashlib.sha256(f"synthetic-ksv-{i}".encode()).hexdigest()[:48]
            (kfiles / skey).write_bytes(body)
            ksv = KnowledgeSourceVersion(public_id=f"kv{i:030d}", source_id=ks.id, version=1, state="active", language="en", authority_level=2, publisher="Synthetic Publisher",
                                         provenance_note="Synthetic fixture text for restore drills.", licence_class="public_official", original_filename=f"synthetic-{i}.txt",
                                         storage_key=skey, media_type="text/plain", byte_size=len(body), checksum_sha256=_sha(body), scan_status="scan_passed", chunk_count=len(texts),
                                         approved_by_user_id=approver, approved_at=now)
            s.add(ksv)
            s.flush()
            s.add(KnowledgeIndexRecord(version_id=ksv.id, collection=KP.COLLECTION, embedder="local", chunk_count=len(texts), state="built", built_at=now))
            for j, text in enumerate(texts):
                cid = f"{ksv.public_id}-c{j}"
                chunks.append(DocumentChunk(chunk_id=cid, doc_id=ksv.public_id, text=text, position=j,
                                            metadata={"doc_id": ksv.public_id, "chunk_index": j, "source_version": ksv.public_id, "language": "en"}))
        s.commit()
    store = ChromaStore(LocalHashEmbedder(), persist_dir=str(kindex), collection_name=KP.COLLECTION)
    store.add_chunks(chunks)
    engine.dispose()
    return Source(database_url=url, documents_dir=docs, knowledge_files_dir=kfiles, knowledge_index_dir=kindex)
