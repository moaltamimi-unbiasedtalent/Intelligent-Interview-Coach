"""Durable, owner-scoped cancellation/deadline facts. No prompts, arguments or events."""
from __future__ import annotations

import time

from sqlalchemy import select, update

from src.persistence import AgentRunControl


class RunControlStore:
    def __init__(self, session_factory, clock=time.time):
        self.sf, self.clock = session_factory, clock

    def create(self, run_id: str, owner: str, timeout_s: int = 180) -> None:
        with self.sf() as s:
            s.add(AgentRunControl(run_id=run_id, owner_user_id=int(owner), status="running",
                                  settled=False, deadline_epoch=self.clock() + timeout_s))
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
