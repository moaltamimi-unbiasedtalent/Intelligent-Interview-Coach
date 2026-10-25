"""Durable, owner-scoped cancellation/deadline facts. No prompts, arguments or events."""
from __future__ import annotations

import time

from sqlalchemy import case, inspect, select, update
from sqlalchemy.exc import IntegrityError

from src.persistence import AgentRunControl


class RunAdmissionConflict(Exception):
    """The durable run cannot be claimed by this caller now."""


class RunControlStore:
    def __init__(self, session_factory, clock=time.time):
        self.sf, self.clock = session_factory, clock

    def create(self, run_id: str, owner: str, timeout_s: int = 180) -> None:
        with self.sf() as s:
            from src.backup_set.admission import pending_session

            if pending_session(s):
                raise RunAdmissionConflict()
            s.add(AgentRunControl(run_id=run_id, owner_user_id=int(owner), status="running",
                                  settled=False, deadline_epoch=self.clock() + timeout_s))
            s.commit()

    def available(self) -> bool:
        with self.sf() as s:
            return inspect(s.get_bind()).has_table("agent_run_controls")

    def claim(self, run_id: str, owner: str, *, required: bool, timeout_s: int = 180) -> dict | None:
        """Atomic producer admission. Never reclaim an unsettled/expired/failed producer.

        Historical synchronous threads may acquire their first control row only
        after the service has verified checkpoint ownership. A missing required
        row/table always refuses. No lease expiry or automatic process-loss retry.
        """
        from src.backup_set.admission import pending

        if pending(self.sf):
            raise RunAdmissionConflict()
        if not self.available():
            if required:
                raise RunAdmissionConflict()
            return None  # pre-0048 synchronous compatibility
        with self.sf() as s:
            row = s.get(AgentRunControl, run_id)
            if row is None:
                if required:
                    raise RunAdmissionConflict()
                s.add(AgentRunControl(run_id=run_id, owner_user_id=int(owner), status="running",
                                      settled=False, deadline_epoch=self.clock() + timeout_s))
                try:
                    s.commit()  # the unique PK serializes historical first admission
                except IntegrityError as exc:
                    s.rollback()
                    raise RunAdmissionConflict() from exc
                return {"status": "completed", "deadline_epoch": self.clock() + timeout_s}
            previous = {"status": "completed", "deadline_epoch": row.deadline_epoch}
            claimed = s.execute(update(AgentRunControl).where(
                AgentRunControl.run_id == run_id, AgentRunControl.owner_user_id == int(owner),
                AgentRunControl.status == "completed", AgentRunControl.settled.is_(True)
            ).values(status="running", settled=False, deadline_epoch=self.clock() + timeout_s))
            if claimed.rowcount != 1:
                s.rollback()
                raise RunAdmissionConflict()
            s.commit()  # commit before any checkpoint mutation / provider work
            return previous

    def release_unstarted(self, run_id: str, owner: str, previous: dict) -> None:
        """A validation-only refusal is retryable; never erase a concurrent Stop."""
        with self.sf() as s:
            s.execute(update(AgentRunControl).where(
                AgentRunControl.run_id == run_id, AgentRunControl.owner_user_id == int(owner),
                AgentRunControl.settled.is_(False)
            ).values(status=case((AgentRunControl.status == "running", previous["status"]),
                                 else_=AgentRunControl.status),
                     settled=True, deadline_epoch=previous["deadline_epoch"]))
            s.commit()

    def owned(self, run_id: str, owner: str) -> dict | None:
        with self.sf() as s:
            row = s.scalar(select(AgentRunControl).where(AgentRunControl.run_id == run_id,
                                                         AgentRunControl.owner_user_id == int(owner)))
            return {"run_id": row.run_id, "status": row.status, "settled": row.settled,
                    "deadline_epoch": row.deadline_epoch} if row else None

    def probe(self, run_id: str) -> str | None:
        # A store failure propagates; callers fail closed before model/tool execution.
        with self.sf() as s:
            # Older databases support synchronous runs without migration 0048.
            # A controlled thread still fails closed: authorizer.run_control
            # requires a row and interprets None as expired when required=True.
            if not inspect(s.get_bind()).has_table("agent_run_controls"):
                return None
            row = s.get(AgentRunControl, run_id)
            if row is None:
                return None  # synchronous / historical run, not controlled here
            if row.status == "running" and self.clock() >= row.deadline_epoch:
                s.execute(update(AgentRunControl).where(AgentRunControl.run_id == run_id,
                          AgentRunControl.status == "running").values(status="expired"))
                s.commit()
                return "expired"
            return row.status

    def cancel(self, run_id: str, owner: str) -> dict | None:
        with self.sf() as s:
            s.execute(update(AgentRunControl).where(AgentRunControl.run_id == run_id,
                      AgentRunControl.owner_user_id == int(owner), AgentRunControl.status == "running",
                      AgentRunControl.settled.is_(False)).values(status="cancelled"))
            s.commit()
        return self.owned(run_id, owner)

    def interrupt(self, run_id: str) -> None:
        """A process interruption leaves usage explicitly unsettled, never zero."""
        with self.sf() as s:
            s.execute(update(AgentRunControl).where(AgentRunControl.run_id == run_id).values(status="failed", settled=False))
            s.commit()

    def finish(self, run_id: str, failed: bool = False) -> None:
        with self.sf() as s:
            s.execute(update(AgentRunControl).where(AgentRunControl.run_id == run_id,
                      AgentRunControl.status == "running").values(status="failed" if failed else "completed"))
            s.execute(update(AgentRunControl).where(AgentRunControl.run_id == run_id).values(settled=True))
            s.commit()
