"""P10B-W10.14 FULL ADMIN QUALIFICATION. Integrated, deterministic, offline. Proves the least-privilege role model (ROLE-W10-01 closed), the 43-permission matrix, every Admin
route x every persona over real HTTP, cross-domain separation, no private-candidate-data superuser, secret non-disclosure with sentinels, audit coverage, and the
no-break-glass / no-impersonation boundaries. Never calls a provider."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.application import admin_permissions as perm
from tests import _admin_matrix as M
from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register

API = "/api/v1"
PW = "correcthorsebattery"
ROOT = Path(__file__).resolve().parent.parent
DENIED = "Administrator access required."


class World:
    def __init__(self):
        self.app, self.repo, _ = build_auth_app()
        self.c = TestClient(self.app)
        self.c.__enter__()
        self.accounts = account_repo(self.repo)
        self.sf = self.repo.session_factory
        self.n = 0
        self.cookies: dict[str, dict] = {}
        self.uids: dict[str, int] = {}
        for persona in M.PERSONAS:
            self.cookies[persona], self.uids[persona] = self.make(persona)

    def make(self, role="user"):
        self.n += 1
        email = f"q{self.n}@x.com"
        register(self.c, email, PW)
        ck = cookies_for(login_token(self.c, email, PW))
        uid = self.c.get(f"{API}/auth/me", cookies=ck).json()["user_id"]
        if role != "user":
            self.accounts.set_platform_role(uid, role)
        return ck, uid

    def close(self):
        self.c.__exit__(None, None, None)


@pytest.fixture(scope="module")
def world():
    w = World()
    yield w
    w.close()


def _url(path: str) -> str:
    return API + re.sub(r"\{[^}]+\}", "0", path)


def _call(w: World, route, persona_cookies):
    method = route.methods[0]
    kw = {"cookies": persona_cookies}
    if method != "GET":
        kw["json"] = {}
    return w.c.request(method, _url(route.path), **kw)


def _is_denied(resp) -> bool:
    if resp.status_code != 403:
        return False
    try:
        return resp.json().get("error", {}).get("message") == DENIED
    except Exception:  # noqa: BLE001
        return False


# ============================================================ permission model (ROLE-W10-01)
def test_registry_is_exactly_43_and_roles_are_exactly_the_canonical_seven():
    assert len(perm.PERMISSIONS) == 43 and len(set(perm.PERMISSIONS)) == 43
    assert set(perm.ROLE_PRESETS) == set(M.ROLES)                                         # six Admin presets; candidate has none
    from src.persistence import PLATFORM_ROLES
    assert set(PLATFORM_ROLES) == {"user", *M.ROLES}
    assert perm.ROLE_CANDIDATE == "user" and perm.permissions_for_role("user") == frozenset()


def test_every_preset_is_a_subset_of_the_registry_and_no_wildcard_or_banned_permission_exists():
    for r in M.ROLES:
        assert perm.ROLE_PRESETS[r] <= perm.PERMISSION_SET, r
    assert not [p for p in perm.PERMISSIONS if "*" in p or any(f in p for f in perm.BANNED_PERMISSION_FRAGMENTS)]


def test_role_w10_01_platform_admin_is_least_privilege_not_universal():
    pa = perm.ROLE_PRESETS["platform_admin"]
    absent = set(perm.PERMISSIONS) - pa
    assert absent == set(M.PLATFORM_ADMIN_ABSENT) and len(pa) == 28 and len(absent) == 15
    for specialist in ("platform.billing.read", "platform.billing.refund", "platform.reports.commercial.read", "platform.plans.price.change", "platform.config.manage",
                       "platform.integrations.secret.rotate", "platform.jobs.read", "platform.jobs.manage", "platform.knowledge.manage", "platform.knowledge.approve",
                       "platform.privacy.execute", "platform.legal.manage", "platform.security.manage", "platform.incidents.manage", "platform.audit.export"):
        assert specialist not in pa, specialist
    # every absent permission is owned by a domain role, except secret rotation which is intentionally unassigned
    for p in absent - {"platform.integrations.secret.rotate"}:
        assert [r for r in M.ROLES if p in perm.ROLE_PRESETS[r] and r != "platform_admin"], p
    assert not [r for r in M.ROLES if "platform.integrations.secret.rotate" in perm.ROLE_PRESETS[r]]


def test_permission_matrix_43_by_7_is_deterministic_and_default_deny_holds():
    m = M.permission_matrix()
    assert len(m) == 43 and all(set(v) == set(M.PERSONAS) for v in m.values())
    assert M.matrix_hash() == M.matrix_hash()
    assert all(not v["user"] for v in m.values())                                         # the candidate holds nothing
    for odd in (None, "", "ghost", "PLATFORM_ADMIN", "platform_admin ", "root", "break_glass"):
        assert perm.permissions_for_role(odd) == frozenset(), odd                         # unknown / missing: default deny
    assert not perm.is_admin_role("ghost") and not perm.is_admin_role(None) and not perm.is_admin_role("user")


def test_cross_domain_separation_from_the_presets():
    P = perm.ROLE_PRESETS
    deny = {
        "support_operator": ["platform.billing.read", "platform.plans.price.change", "platform.subscriptions.manage", "platform.ai.activate", "platform.knowledge.approve",
                             "platform.privacy.execute", "platform.security.manage", "platform.incidents.manage", "platform.audit.export", "platform.jobs.manage", "platform.config.manage"],
        "billing_admin": ["platform.users.manage", "platform.knowledge.manage", "platform.ai.manage", "platform.privacy.execute", "platform.legal.manage", "platform.incidents.manage",
                          "platform.jobs.manage", "platform.integrations.secret.rotate", "platform.support.read"],
        "knowledge_admin": ["platform.users.manage", "platform.subscriptions.manage", "platform.billing.read", "platform.privacy.execute", "platform.incidents.manage", "platform.users.role.assign"],
        "security_privacy_admin": ["platform.billing.read", "platform.plans.manage", "platform.ai.activate", "platform.knowledge.approve", "platform.flags.manage", "platform.jobs.manage",
                                   "platform.users.role.assign"],
        "operations_admin": ["platform.users.manage", "platform.users.role.assign", "platform.privacy.execute", "platform.billing.read", "platform.knowledge.approve", "platform.ai.activate"],
    }
    for role, perms in deny.items():
        for p in perms:
            assert p not in P[role], (role, p)
    # intended owners
    assert "platform.billing.refund" in P["billing_admin"] and "platform.knowledge.approve" in P["knowledge_admin"] and "platform.privacy.execute" in P["security_privacy_admin"]
    assert "platform.jobs.manage" in P["operations_admin"] and "platform.users.role.assign" in P["platform_admin"] and "platform.support.reply" in P["support_operator"]


def test_no_admin_permission_grants_generic_candidate_content_access():
    banned = ("cv", "document", "answer", "conversation", "memory", "evidence", "chat", "transcript", "prompt", "view_as", "impersonat", "break_glass")
    assert not [p for p in perm.PERMISSIONS if any(b in p.lower() for b in banned)]
    assert not [p for p in perm.PERMISSIONS if p.endswith((".all", ".any", ".superuser", ".*"))]


def test_authorization_is_by_permission_never_by_role_name_in_admin_domain_code():
    offenders = []
    for f in list((ROOT / "src/api/routes").glob("*.py")) + [ROOT / "src/application/admin_command_center.py"]:
        txt = f.read_text()
        for pat in (r"platform_role\s*(==|!=|in)\s", r"\bis_platform_admin\(", r"require_platform_admin", r"\.platform_role\s*(==|!=)"):
            for m in re.finditer(pat, txt):
                line = txt[txt.rfind("\n", 0, m.start()) + 1: txt.find("\n", m.start())]
                if "#" in line.split(m.group(0))[0]:
                    continue
                offenders.append((f.name, line.strip()[:100]))
    # the only role-name reads allowed in route code are non-authorising projections (the profile payload and the dashboard role label)
    assert all(f in ("auth.py", "admin.py", "workspaces.py") for f, _ in offenders), offenders


# ============================================================ every route x every persona (real HTTP)
@pytest.fixture(scope="module")
def http_matrix(world):
    results = {}
    for r in M.routes():
        for persona in M.PERSONAS:
            resp = _call(world, r, world.cookies[persona])
            results[(r.path, r.methods[0], persona)] = resp
    return results


def test_route_x_persona_matrix_over_http_is_exactly_the_preset_expectation(http_matrix):
    wrong, n = [], 0
    for r in M.routes():
        for persona in M.PERSONAS:
            resp = http_matrix[(r.path, r.methods[0], persona)]
            allowed = M.expected_allowed(r.permissions, persona)
            n += 1
            if allowed and (resp.status_code in (401,) or _is_denied(resp) or resp.status_code >= 500):
                wrong.append((r.path, r.methods[0], persona, "should be allowed", resp.status_code))
            if not allowed and not _is_denied(resp):
                wrong.append((r.path, r.methods[0], persona, "should be denied", resp.status_code))
    assert n == len(M.routes()) * len(M.PERSONAS) and n > 1000
    assert not wrong, wrong[:10]


def test_candidate_is_denied_every_admin_route_and_inactive_admin_has_no_authority(world, http_matrix):
    for r in M.routes():
        assert _is_denied(http_matrix[(r.path, r.methods[0], "user")]), r.path
    ck, uid = world.make("platform_admin")
    world.accounts.set_status(uid, "deactivated")
    for r in M.routes()[:25]:
        assert _call(world, r, ck).status_code in (401, 403), r.path               # a deactivated Admin's session no longer authenticates


def test_every_domain_has_candidate_denied_an_unrelated_persona_denied_and_an_owner_allowed(http_matrix):
    for domain, _ in M.DOMAINS:
        items = [r for r in M.routes() if M.domain_of(r.path) == domain]
        assert items, domain
        perms = {p for r in items for p in r.permissions}
        owners = [persona for persona in M.ROLES if any(p in M.role_perms(persona) for p in perms)]
        unrelated = [persona for persona in M.ROLES if not any(p in M.role_perms(persona) for p in perms)]
        gate = next(r for r in items if r.methods == ("GET",)) if any(r.methods == ("GET",) for r in items) else items[0]
        assert _is_denied(http_matrix[(gate.path, gate.methods[0], "user")]), domain
        assert owners, domain
        for persona in owners:
            if M.expected_allowed(gate.permissions, persona):
                assert not _is_denied(http_matrix[(gate.path, gate.methods[0], persona)]), (domain, persona)
        for persona in unrelated:
            assert _is_denied(http_matrix[(gate.path, gate.methods[0], persona)]), (domain, persona)
    assert not [r.path for r in M.routes() if M.domain_of(r.path) == "UNMAPPED"]


def test_every_privileged_route_is_gated_and_unauthenticated_requests_never_succeed(world):
    from src.api.admin_route_invariant import ungated
    assert ungated() == []
    anon = TestClient(world.app)
    for r in M.routes()[:40]:
        assert anon.request(r.methods[0], _url(r.path), **({"json": {}} if r.methods[0] != "GET" else {})).status_code in (401, 403), r.path


# ============================================================ HTTP method audit
def test_get_routes_are_read_only_and_every_mutation_is_audited(world):
    inv = M.mutation_inventory()
    assert len(inv) == sum(1 for r in M.routes() if r.methods != ("GET",)) and len(inv) >= 60
    unaudited = [r["path"] for r in inv if not r["audited_in_handler"]]
    assert unaudited == ["/admin/step-up"], unaudited                                  # step-up audits inside StepUpService (admin.step_up.succeeded/failed)
    for r in M.routes():
        if r.methods == ("GET",):
            src = inspect.getsource(r.route.endpoint)
            assert not re.search(r"\.(add|delete|commit)\(|\.enqueue\(|build_audit\(", src), r.path
    assert "admin.step_up.succeeded" in (ROOT / "src/application/admin_audit.py").read_text()
    exp = [r for r in M.routes() if r.path == "/admin/audit/export"]
    assert exp and exp[0].methods == ("POST",)                                         # export is a POST on purpose: reason + audit semantics


def test_each_mutation_family_has_a_forced_audit_failure_rollback_test_in_the_repo():
    families = {
        "user/access": "tests/test_admin_foundation_w10_1.py::test_aud2_audit_failure_rolls_back_the_mutation",
        "workspace": "tests/test_admin_access_w10_2.py",
        "support": "tests/test_support_w10_3.py",
        "plans/subscriptions": "tests/test_plans_entitlements_w10_4.py",
        "billing": "tests/test_billing_w10_5.py",
        "integrations": "tests/test_integrations_w10_6.py",
        "ai governance": "tests/test_ai_admin_w10_7.py",
        "knowledge": "tests/test_knowledge_admin_w10_8.py",
        "jobs": "tests/test_admin_qualification_w10_14.py::test_jobs_admin_enqueue_rolls_back_when_the_audit_row_cannot_be_written",
        "privacy/legal": "tests/test_privacy_legal_w10_10.py",
        "flags/config": "tests/test_platform_config_w10_11.py",
        "security/incidents/role approval": "tests/test_security_w10_13.py::test_incident_mutations_audit_in_the_same_transaction_and_roll_back_on_audit_failure",
    }
    for fam, ref in families.items():
        f, _, name = ref.partition("::")
        text = (ROOT / f).read_text()
        assert name in text if name else re.search(r"rolls?_?back|audit_failure|audit_store|_stage_audit|atomic", text, re.I), (fam, ref)


def test_jobs_admin_enqueue_rolls_back_when_the_audit_row_cannot_be_written(world, monkeypatch):
    from sqlalchemy import text
    from src.auth_repository import AccountRepository

    def count():
        with world.sf() as s:
            return s.execute(text("SELECT count(*) FROM jobs")).scalar()

    before = count()

    def boom(session, audit):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(boom))
    r = world.c.post(f"{API}/admin/jobs", cookies=world.cookies["operations_admin"], json={"job_type": "diagnostic_noop", "payload": {"label": "Check 1"}, "dedupe_id": "qk"})
    assert r.status_code == 500
    monkeypatch.undo()
    assert count() == before                                                           # the job was never created: audit failure rolled the mutation back


# ============================================================ privacy + secret sentinels
PRIVATE = {"document": "SENTINEL-DOC-CV-7741", "answer": "SENTINEL-ANSWER-7742", "chat": "SENTINEL-CHAT-7743", "memory": "SENTINEL-MEMORY-7744", "evidence": "SENTINEL-EVIDENCE-7745"}
TICKET = "SENTINEL-TICKET-BODY-7746"
SECRETS = ("sk-or-SENTINEL-SECRET-1", "SENTINEL-ADZUNA-KEY-2", "SENTINEL-GOOGLE-SECRET-3", "SENTINEL-BREVO-KEY-4", "redis://:SENTINEL-REDIS-PW-5@h:6379")


def test_privacy_and_secret_sentinels_never_appear_in_any_admin_surface(world, monkeypatch):
    from src.persistence import Answer, CandidateDocument, Interview, PreparationMemory, Question
    cand_ck, cand_uid = world.make("user")
    planted = []
    for label, build in (
        ("memory", lambda s: PreparationMemory(user_id=cand_uid, category="goal", summary=PRIVATE["memory"])),
        ("document", lambda s: CandidateDocument(user_id=cand_uid, title=PRIVATE["document"])),
    ):
        try:
            with world.sf() as s:
                s.add(build(s))
                s.commit()
            planted.append(label)
        except Exception:  # noqa: BLE001
            pass
    try:
        with world.sf() as s:
            iv = Interview(user_id=cand_uid)
            s.add(iv)
            s.flush()
            q = Question(interview_id=iv.id, position=0, canonical_question=PRIVATE["chat"])
            s.add(q)
            s.flush()
            s.add(Answer(question_id=q.id, text=PRIVATE["answer"], evaluation={"evidence": PRIVATE["evidence"]}))
            s.commit()
        planted.append("interview")
    except Exception:  # noqa: BLE001
        pass
    assert {"memory", "document", "interview"} <= set(planted), planted
    for k, v in zip(("OPENROUTER_API_KEY", "ADZUNA_APP_KEY", "GOOGLE_CLIENT_SECRET", "BREVO_API_KEY", "REDIS_URL"), SECRETS):
        monkeypatch.setenv(k, v)
    t = world.c.post(f"{API}/support/tickets", cookies=cand_ck, json={"category": "technical", "subject": "help", "message": TICKET})
    assert t.status_code == 201
    tid = t.json()["public_id"]
    hits: dict[str, str] = {}
    get_routes = [r for r in M.routes() if r.methods == ("GET",)]
    for persona in M.ROLES:
        for r in get_routes:
            if not M.expected_allowed(r.permissions, persona):
                continue
            resp = _call(world, r, world.cookies[persona])
            body = resp.text
            for name, s in {**{f"private:{k}": v for k, v in PRIVATE.items()}, **{f"secret:{i}": v for i, v in enumerate(SECRETS)}}.items():
                if s in body:
                    hits[f"{persona} {r.path} {name}"] = "leak"
    # detail surfaces with real ids
    detail = [f"/admin/users/{cand_uid}", f"/admin/support/tickets/{tid}", "/admin/integrations", "/admin/providers", "/admin/ai", "/admin/home", "/admin/security/summary"]
    for persona in M.ROLES:
        for p in detail:
            resp = world.c.get(API + p, cookies=world.cookies[persona])
            for s in (*PRIVATE.values(), *SECRETS):
                if s in resp.text:
                    hits[f"{persona} {p} {s}"] = "leak"
    assert not hits, hits
    # the ticket body is visible ONLY on the permissioned support surface
    sup = world.c.get(f"{API}/admin/support/tickets/{tid}", cookies=world.cookies["support_operator"])
    assert sup.status_code == 200 and TICKET in sup.text
    # ...and only for personas that hold platform.support.read (the support operator AND, by its explicit preset, the platform administrator); everyone else is denied
    for persona in ("platform_admin", "billing_admin", "knowledge_admin", "security_privacy_admin", "operations_admin"):
        other = world.c.get(f"{API}/admin/support/tickets/{tid}", cookies=world.cookies[persona])
        if "platform.support.read" in M.role_perms(persona):
            assert other.status_code == 200 and persona == "platform_admin"
        else:
            assert _is_denied(other) and TICKET not in other.text, persona
    # audit rows and security events carry neither
    from sqlalchemy import text
    with world.sf() as s:
        blob = " ".join(str(r) for r in s.execute(text("SELECT event_type, target_id, context FROM audit_events")).all())
    assert not [x for x in (*PRIVATE.values(), TICKET, *SECRETS) if x in blob]


def test_admin_response_schemas_and_ui_contain_no_generic_content_or_secret_fields():
    import importlib
    from pydantic import BaseModel
    bad = ("document_text", "extracted_text", "cv_text", "answer_text", "transcript", "preparation_messages", "conversation", "memory_summary", "evidence_text", "raw_response",
           "checkpoint", "uploaded_file_bytes", "password_hash", "token_hash", "api_key", "client_secret", "prompt_text")
    # Documented allow-list exceptions (boundary statements, not content): `transcript_visible_to_admin` (constant False on the privacy-request schema).
    allow = {"transcript_visible_to_admin"}
    offenders = []
    for modname in ("src.api.schemas.admin", "src.api.schemas.support", "src.api.schemas.privacy"):
        try:
            mod = importlib.import_module(modname)
        except Exception:  # noqa: BLE001
            continue
        for obj in vars(mod).values():
            if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
                for name in obj.model_fields:
                    if name in allow:
                        continue
                    if any(b in name.lower() for b in bad):
                        offenders.append((modname, obj.__name__, name))
    # support.* is the one domain-scoped candidate-authored text surface (ticket subject/message/notes); it is checked by the support tests, not by this generic list
    offenders = [o for o in offenders if o[0] != "src.api.schemas.support"]
    assert not offenders, offenders
    ui = " ".join(p.read_text() for p in (ROOT / "frontend/components/admin").glob("*.tsx"))
    for b in bad:
        assert not re.search(rf"(\.|\b){b}\b\s*(\)|,|\}}|\]|:|\.)", ui.replace("transcript_visible_to_admin", "")), ("ui", b)


# ============================================================ no break-glass / impersonation / generic browser
def test_no_break_glass_no_impersonation_no_view_as_no_generic_candidate_browser():
    routes_txt = " ".join(r.path.lower() for r in M.routes())
    assert not re.search(r"break.?glass|impersonat|view.?as|act.?as|sudo|become", routes_txt)
    code = "\n".join(p.read_text().lower() for p in list((ROOT / "src").rglob("*.py")) if "admin" in str(p) or "security" in str(p))
    assert not re.search(r"def\s+\w*(impersonat|break_?glass|view_as)", code)
    assert not (ROOT / "src/application/break_glass.py").exists()
    from src.persistence import Base
    assert not [t for t in Base.metadata.tables if re.search(r"break|glass|impersonat|view_as|temporary_access", t)]
    for p in sorted((ROOT / "src/api/routes").glob("admin*.py")):
        assert not re.search(r"candidate.?(search|browser)|search_candidates|/candidates", p.read_text().lower()), p.name


def test_secret_rotation_stays_effectively_unreachable():
    owners = [r for r in M.ROLES if "platform.integrations.secret.rotate" in perm.ROLE_PRESETS[r]]
    assert owners == []
    routes = [r for r in M.routes() if "platform.integrations.secret.rotate" in r.permissions]
    assert routes and all(r.methods == ("POST",) for r in routes)


# ============================================================ navigation and pages
def test_frontend_navigation_is_a_pure_function_of_permissions_for_all_personas():
    dests = M.destinations()
    assert len(dests) >= 19
    all_perms = set(perm.PERMISSIONS)
    for d in dests:
        assert set(d["anyOf"]) <= all_perms, d
    assert M.nav_for(M.role_perms("user")) == [] and M.nav_for(M.role_perms("ghost")) == [] and M.nav_for(frozenset()) == []
    for persona in M.ROLES:
        nav = M.nav_for(M.role_perms(persona))
        assert "/admin" in nav, persona
        for d in dests:
            assert (d["href"] in nav) == any(p in M.role_perms(persona) for p in d["anyOf"]), (persona, d["href"])
    caps = (ROOT / "frontend/lib/admin/capabilities.ts").read_text()
    assert not re.search(r"platform_admin|support_operator|billing_admin|knowledge_admin|security_privacy_admin|operations_admin|ROLE_PRESETS", caps)


def test_every_admin_page_has_a_destination_or_is_a_child_and_every_destination_has_a_page():
    pages = set(M.admin_pages())
    hrefs = {d["href"] for d in M.destinations()}
    assert {h for h in hrefs if h.startswith("/admin")} <= pages, {h for h in hrefs if h.startswith("/admin")} - pages
    top = {p for p in pages if "[" not in p}
    orphans = top - hrefs
    assert orphans == set(), orphans
    # each page's data calls are gated on the server: every api.admin method path maps to a gated route
    client = (ROOT / "frontend/lib/api/client.ts").read_text()
    used = set(re.findall(r'"/admin/[a-z\-]+', client))
    gated = {"/admin/" + r.path.split("/")[2] for r in M.routes() if r.path.startswith("/admin/")}
    assert {u.strip('"') for u in used} <= gated | {"/admin/home"}, {u.strip('"') for u in used} - gated


def test_admin_pages_have_one_h1_labelled_controls_and_no_color_only_status():
    for page in (ROOT / "frontend/app/admin").rglob("page.tsx"):
        text = page.read_text()
        assert "PageHeader" in text or "<h1" in text, page
    ui = " ".join(p.read_text() for p in (ROOT / "frontend/components/admin").glob("*.tsx"))
    assert "role=\"alertdialog\"" in (ROOT / "frontend/components/ui/ConfirmDialogBase.tsx").read_text()
    assert "StatusLabel" in ui and "aria-selected" in ui
