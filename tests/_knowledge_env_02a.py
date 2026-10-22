"""Shared harness for the 02A persistence, identity and recovery suites. Offline and deterministic: file-backed SQLite and a real PERSISTENT
Chroma store under a temp root, the local hashing embedder, the fake scanner. ``Process`` is one simulated process (API + worker objects);
building a second ``Process`` over the same root is a restart or a redeployment, because nothing but the files on disk is shared."""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from src.copilot.config import CopilotConfig
from pydantic import SecretStr

from src.copilot.embeddings import BaseEmbedder, LocalHashEmbedder
from src.copilot.vectorstore import ChromaStore, InMemoryVectorStore
from src.documents.file_security import FakeScanner
from src.documents.storage import LocalDocumentStore
from src.jobs.service import JobService
from src.jobs.worker import Worker
from src.knowledge_admin import policy as P
from src.knowledge_admin.alerts import observe_guard_report
from src.knowledge_admin.config import KnowledgeRuntimeConfig
from src.knowledge_admin.environment import KnowledgeServingGuard, build_identity, worker_id_for
from src.knowledge_admin.readiness import KnowledgeReadinessService
from src.knowledge_admin.retriever import GovernedKnowledgeRetriever
from src.knowledge_admin.runtime import KnowledgeRuntime
from src.knowledge_admin.service import KnowledgeAdminService
from src.persistence import init_db, make_engine, make_session_factory, utcnow

DOC = ("Digital product managers prioritise a roadmap using customer evidence. A product manager defines outcomes, "
       "works with engineering, and measures adoption.\n\nInterview preparation for product roles covers prioritisation frameworks.")
DOC2 = DOC + "\n\nA second edition adds a section on discovery interviews and opportunity solution trees."
META = dict(language="en", authority_level=2, publisher="Example Framework Body", source_url="https://example.org/framework",
            provenance_note="Published public framework; downloaded 2026-10-01.", licence_class="public_official")
QUERY = "How should I prioritise a roadmap using customer evidence?"
OTHER_TEMP = "/nonexistent-temp-root-for-02a-tests"      # patched in as tempfile.gettempdir() so a hosted guard does not see pytest's tmp_path as "temporary"


class FakeSemanticEmbedder(BaseEmbedder):
    """02B: an offline stand-in for an APPROVED semantic embedder (provider ``openai``) so hosted-environment tests exercise the guard's other
    findings. It reuses the deterministic hash vectors for scoring; only its identity differs. NEVER a real provider call."""

    provider = "openai"
    model = "fake-semantic-test"
    version = "test-1"
    dimensions = 512

    def __init__(self):
        self._h = LocalHashEmbedder()

    def embed_documents(self, texts):
        return self._h.embed_documents(texts)

    def embed_query(self, text):
        return self._h.embed_query(text)


class Clock:
    def __init__(self):
        self.now = utcnow()

    def __call__(self):
        return self.now


class PersistentLikeStore(InMemoryVectorStore):
    """An in-process store that DECLARES a persist_dir (so guards see it as persistent) without touching a disk. Only for guard unit tests."""

    def __init__(self, embedder, persist_dir="persistent-like"):
        super().__init__(embedder)
        self.persist_dir = persist_dir
        self.collection_name = P.COLLECTION


PG_URL = "postgresql+psycopg://knowledge:not-a-real-password@db.internal:5432/ask4mo"     # only ever fingerprinted by the guard, never connected


def runtime_config(root: Path, *, environment="development", data_root: Path | None = None, explicit_files=False, database_url=None) -> KnowledgeRuntimeConfig:
    dr = Path(data_root or root)
    return KnowledgeRuntimeConfig(database_url=database_url or f"sqlite:///{root / 'kb.db'}", data_root=str(dr), chroma_dir=str(root / "chroma"),
                                  private_files_dir=str(root / "private"), environment=environment, private_files_explicit=explicit_files)


class Process:
    """One simulated API+worker process over ``root``. ``store`` may be injected (a deliberately different or empty one)."""

    def __init__(self, root: Path, *, environment="development", data_root: Path | None = None, store=None, clock=None, embedding=None,
                 worker_environment=None, worker_data_root: Path | None = None, with_guard=True, ttl=0, alerts=False, hosted_sqlite=False):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.engine = make_engine(f"sqlite:///{self.root / 'kb.db'}")
        init_db(self.engine)
        self.sf = make_session_factory(self.engine)
        self.clock = clock or Clock()
        self.jobs = JobService(self.sf, clock=self.clock)
        self.docs = LocalDocumentStore(str(self.root / "private"))
        hosted = environment != "development"
        # 02B: a hosted environment never accepts the lexical hash embedder, so hosted processes run an offline stand-in for an approved semantic one
        embedding = embedding or ("openai" if hosted else "local")
        self.config = CopilotConfig(embedding_provider=embedding, chroma_persist_dir=str(self.root / "chroma"), api_key=None,
                                    embedding_api_key=SecretStr("test-key-not-real") if embedding == "openai" else None)
        self.store = store or ChromaStore(FakeSemanticEmbedder() if hosted else LocalHashEmbedder(), persist_dir=str(self.root / "chroma"), collection_name=P.COLLECTION)
        self.runtime_cfg = runtime_config(self.root, environment=environment, data_root=data_root,
                                          database_url=PG_URL if environment != "development" and not hosted_sqlite else None)
        self.guard = (KnowledgeServingGuard(self.sf, self.runtime_cfg, store_provider=lambda: self.store, doc_store=self.docs, job_service=self.jobs,
                                            copilot_config=self.config, ttl_seconds=ttl,
                                            on_report=(lambda r: observe_guard_report(self.sf, r)) if alerts else None) if with_guard else None)
        self.svc = KnowledgeAdminService(self.sf, doc_store=self.docs, jobs=self.jobs, clock=self.clock, guard=self.guard)
        self.krt = KnowledgeRuntime(session_factory=self.sf, doc_store=self.docs, scanner=FakeScanner(), vector_store_factory=lambda: self.store,
                                    clock=self.clock)
        # The worker records ITS environment through its heartbeat id; by default it is the same environment as the API.
        wcfg = replace(self.runtime_cfg, environment=worker_environment or environment,
                       data_root=str(worker_data_root or self.runtime_cfg.data_root))
        self.worker_id = worker_id_for(build_identity(wcfg, self.config), rand="abcdef")
        self.worker = Worker(self.jobs, clock=self.clock, worker_id=self.worker_id, services=SimpleNamespace(knowledge=self.krt))
        self.retriever = GovernedKnowledgeRetriever(self.store, self.sf, guard=self.guard)
        self.readiness = KnowledgeReadinessService(self.sf, governed_provider=lambda: self.retriever,
                                                   curated_store_provider=lambda: InMemoryVectorStore(LocalHashEmbedder()),
                                                   job_service=self.jobs, config=self.config, guard=self.guard)

    def close(self):
        self.engine.dispose()
        release_chroma()

    # ------------------------------------------------------------ helpers
    def drain(self, limit=30):
        out = []
        for _ in range(limit):
            r = self.worker.run_once()
            if r == "idle":
                break
            out.append(r)
        return out

    def upload(self, *, title="Product framework", name="framework.txt", data=DOC.encode(), **over):
        return self.svc.create_source(title=title, filename=name, data=data, actor_user_id=None, **{**META, **over})

    def new_version(self, source_public_id, *, name="framework2.txt", data=DOC2.encode(), **over):
        return self.svc.add_version(source_public_id, filename=name, data=data, actor_user_id=None, **{**META, **over})

    def to_review(self, **kw):
        r = self.upload(**kw)
        self.drain()
        return r

    def to_indexed(self, **kw):
        r = self.to_review(**kw)
        v = r["version_public_id"]
        self.svc.approve(v, actor_user_id=1)
        self.svc.request_index(v, actor_user_id=1)
        self.drain()
        return r

    def to_active(self, **kw):
        r = self.to_indexed(**kw)
        self.svc.activate(r["version_public_id"], actor_user_id=1)
        return r

    def index_version(self, vpid):
        self.svc.approve(vpid, actor_user_id=1)
        self.svc.request_index(vpid, actor_user_id=1)
        self.drain()

    def state(self, vpid):
        return self.svc.version_detail(vpid)["state"]

    def evidence(self, query=QUERY):
        """Candidate-facing governed retrieval provenance: what a citation would carry."""
        out = []
        for r in self.retriever.retrieve(query, top_k=5):
            m = r.chunk.metadata
            out.append({k: m.get(k) for k in ("title", "knowledge_source_id", "knowledge_version_id", "publisher", "authority_level", "language",
                                              "source_version", "filename", "source_url")} | {"chunk_id": r.chunk.chunk_id})
        return sorted(out, key=lambda e: e["chunk_id"])


def release_chroma() -> None:
    """Stop and forget every Chroma system opened by this process. Chroma's native client can abort the interpreter at exit (a recursive_mutex failure)
    when many persistent clients are left alive; releasing them after each simulated process keeps the suite's exit status deterministic."""
    try:
        from chromadb.api.shared_system_client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
    except Exception:  # noqa: BLE001 - best effort only
        pass


def hosted_temp(monkeypatch):
    """Make tempfile.gettempdir() point elsewhere so pytest's tmp_path is not treated as a temporary directory by the hosted placement check."""
    monkeypatch.setattr(tempfile, "gettempdir", lambda: OTHER_TEMP)
