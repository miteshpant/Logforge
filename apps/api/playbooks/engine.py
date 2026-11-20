"""
Playbook runs (Phase 13): steps in order; an approval step waits for a
person; a failed step stops the run unless it says `on_error: continue`.

The engine does no I/O itself: actions, enrichment, searches, ticket links
and integrations are passed in (the API gives it the real ones, tests give
it fakes), and a run is plain data saved after every change, so a run
waiting for approval survives restarts and is resumed by whichever API
replica the approval reaches.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from integrations import actions, templates

from .model import DEFAULT_APPROVERS, Playbook, duration

FINAL = ("succeeded", "failed", "rejected", "expired")


class RunError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Run:
    id: str
    tenant_id: str
    playbook_id: str
    playbook_name: str
    trigger: str
    trigger_ref: str
    status: str
    steps: List[Dict[str, Any]]
    context: Dict[str, Any]
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Run":
        return cls(**data)

    def waiting_step(self) -> Optional[Dict[str, Any]]:
        return next((s for s in self.steps if s["status"] == "waiting"), None)


@dataclass
class Runner:
    action: Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], Awaitable[actions.ActionResult]]
    enrich: Callable[[str, Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]
    search: Callable[[str, Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]
    link_ticket: Callable[[str, str, Dict[str, Any]], Any]
    integrations: Callable[[str], Dict[str, Dict[str, Any]]]
    clock: Callable[[], datetime] = field(default=_now)

    async def start(self, tenant_id: str, pb: Playbook, trigger: str, ctx: Dict[str, Any], playbook_id: str = "",
                    trigger_ref: str = "") -> Run:
        now = self.clock().isoformat()
        run = Run(id=uuid.uuid4().hex, tenant_id=tenant_id, playbook_id=playbook_id, playbook_name=pb.name,
                  trigger=trigger, trigger_ref=trigger_ref, status="running",
                  steps=[{"id": s.id, "type": s.type, "status": "pending", "output": {}, "error": ""}
                         for s in pb.steps],
                  context=ctx, created_at=now, updated_at=now)
        return await self.advance(run, pb)

    def _ctx(self, run: Run) -> Dict[str, Any]:
        return {**run.context, "steps": {s["id"]: {"status": s["status"], "output": s.get("output") or {}}
                                         for s in run.steps}}

    def _approved_before(self, run: Run, index: int) -> bool:
        """An approved approval step after the previous containment step, before this one."""
        for j in range(index - 1, -1, -1):
            step = run.steps[j]
            if step["type"] == "approval":
                return step["status"] == "done" and bool((step.get("decision") or {}).get("approved"))
            if step.get("containment"):
                return False
        return False

    async def _execute(self, run: Run, step, state: Dict[str, Any], index: int, integrations) -> None:
        """Run one non-approval step; raises on failure."""
        ctx = self._ctx(run)
        if step.type == "action":
            integration = integrations.get(step.spec["integration"])
            if integration is None:
                raise RunError(f"no integration named {step.spec['integration']!r}")
            kind = actions.KINDS.get(integration["kind"])
            if kind and kind.containment:
                state["containment"] = True
                if not self._approved_before(run, index):
                    raise RunError("containment needs an approved approval step before it")
            inputs = templates.render_tree(step.spec.get("inputs") or {}, ctx)
            result = await self.action(integration, inputs, ctx)
            state["output"] = result.output
            if not result.ok:
                raise RunError(result.error or "the action failed")
            if step.link_case and result.output.get("ticket"):
                case_id = (run.context.get("case") or {}).get("id")
                if case_id:
                    self.link_ticket(run.tenant_id, case_id, {**result.output,
                                                              "integration": integration.get("id", "")})
                    state["output"]["linked_case"] = case_id
        elif step.type == "enrich":
            state["output"] = await self.enrich(run.tenant_id, templates.render_tree(step.spec, ctx), ctx)
        elif step.type == "search":
            state["output"] = await self.search(run.tenant_id, templates.render_tree(step.spec, ctx), ctx)

    async def _attempt(self, run: Run, step, state: Dict[str, Any], index: int, integrations) -> bool:
        """Run a step and record its outcome; False if the run must stop here."""
        try:
            await self._execute(run, step, state, index, integrations)
            state["status"] = "done"
        except Exception as e:
            state["status"] = "failed"
            state["error"] = str(e)
            if step.on_error != "continue":
                state["finished_at"] = self.clock().isoformat()
                return False
        state["finished_at"] = self.clock().isoformat()
        return True

    async def advance(self, run: Run, pb: Playbook) -> Run:
        import asyncio

        by_id = {s.id: s for s in pb.steps}
        integrations = None
        index = 0
        while index < len(run.steps):
            state = run.steps[index]
            if state["status"] != "pending":
                index += 1
                continue
            step = by_id[state["id"]]
            # a parallel group: this step and the adjacent pending ones with the same group
            batch = [index]
            if step.parallel:
                while (batch[-1] + 1 < len(run.steps) and run.steps[batch[-1] + 1]["status"] == "pending"
                       and by_id[run.steps[batch[-1] + 1]["id"]].parallel == step.parallel):
                    batch.append(batch[-1] + 1)
            ctx = self._ctx(run)
            todo = []
            for i in batch:
                s_state, s_step = run.steps[i], by_id[run.steps[i]["id"]]
                s_state["started_at"] = self.clock().isoformat()
                if not s_step.applies(ctx):  # its `if` is false: this branch isn't taken
                    s_state["status"] = "skipped"
                    s_state["finished_at"] = s_state["started_at"]
                else:
                    todo.append(i)
            if step.type == "approval" and todo:
                state["status"] = "waiting"
                state["prompt"] = templates.render(step.spec["prompt"], ctx)
                state["approvers"] = step.spec.get("approvers") or DEFAULT_APPROVERS
                state["deadline"] = (self.clock() + duration(step.spec.get("timeout"))).isoformat()
                run.status = "waiting_approval"
                run.updated_at = self.clock().isoformat()
                return run
            if todo:
                if integrations is None and any(by_id[run.steps[i]["id"]].type == "action" for i in todo):
                    integrations = self.integrations(run.tenant_id)
                outcomes = await asyncio.gather(*(self._attempt(run, by_id[run.steps[i]["id"]], run.steps[i], i,
                                                                integrations or {}) for i in todo))
                if not all(outcomes):
                    run.status = "failed"
                    run.updated_at = self.clock().isoformat()
                    return run
            index = batch[-1] + 1
        run.status = "failed" if any(s["status"] == "failed" for s in run.steps) else "succeeded"
        run.updated_at = self.clock().isoformat()
        return run

    def _close(self, run: Run, status: str) -> None:
        for s in run.steps:
            if s["status"] == "pending":
                s["status"] = "skipped"
        run.status = status
        run.updated_at = self.clock().isoformat()

    def expire(self, run: Run) -> bool:
        step = run.waiting_step()
        if step is None or datetime.fromisoformat(step["deadline"]) > self.clock():
            return False
        step["status"] = "expired"
        self._close(run, "expired")
        return True

    async def decide(self, run: Run, pb: Playbook, step_id: str, decision: str, user: str, note: str = "") -> Run:
        if decision not in ("approve", "reject"):
            raise RunError("decision is approve or reject")
        self.expire(run)
        step = run.waiting_step()
        if step is None or step["id"] != step_id:
            raise RunError(f"step {step_id!r} is not waiting for approval (run is {run.status})")
        step["decision"] = {"by": user, "approved": decision == "approve", "note": note,
                            "at": self.clock().isoformat()}
        step["finished_at"] = step["decision"]["at"]
        if decision == "reject":
            step["status"] = "rejected"
            self._close(run, "rejected")
            return run
        step["status"] = "done"
        run.status = "running"
        return await self.advance(run, pb)
