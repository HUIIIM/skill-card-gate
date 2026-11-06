"""send_gate: a human-approval gate for outbound agent actions.

The gate sits between an agent and its tools. Every tool is declared at
one of three tiers in a permissions manifest:

    read   - look, search, fetch. Executes immediately.
    draft  - prepare content that stays inside the system (a draft, a
             local file, a queued post). Executes immediately.
    send   - anything that leaves the system or commits you in front of
             another person: sending mail, posting, messaging, paying.
             NEVER executes on the agent's word alone.

A `send` call does not run. It is recorded as a pending approval request
and the agent gets a receipt, not a result. A human reviews the request
out of band (CLI below, or your own UI on top of the store) and either
approves or denies it. Only an approved request can be executed, exactly
once, through `execute_approved`.

Fail-closed rules, everywhere:

- A tool that is not in the manifest is denied. There is no default tier.
- A missing or corrupt manifest denies everything.
- A missing or corrupt approval store blocks every send execution.
- An approval is single-use: executing twice is denied.
- A denial is final for that request.

Every decision is appended to an audit log (JSON lines) that the gate
never rewrites: executed, blocked_pending, approved, denied, sent,
denied_unknown_tool, denied_replay, store_unavailable.

This is a reference implementation: single process, JSON file store,
standard library only. The security model is the point; swap the store
for your database and the CLI for your UI without changing the rules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

TIERS = ("read", "draft", "send")


class GateError(Exception):
    """Raised when the gate refuses an action. Refusal is the default."""


@dataclass
class GateResult:
    status: str  # executed | pending | denied
    tool: str
    detail: str
    request_id: str | None = None
    value: Any = None


@dataclass
class ApprovalStore:
    """Append-only JSON-lines store for approval requests and decisions."""

    path: Path

    def append(self, event: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def events(self) -> list[dict]:
        if not self.path.exists():
            return []
        events = []
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events

    def request_state(self, request_id: str) -> dict | None:
        """Fold the event log into the current state of one request.

        Only lifecycle events (pending/approved/denied/sent) move a
        request's state. Audit events share the log but are observations
        about the request, never transitions of it, so they are skipped.
        """
        state: dict | None = None
        for event in self.events():
            if event.get("request_id") != request_id:
                continue
            if str(event.get("type", "")).startswith("audit:"):
                continue
            if state is None:
                state = {"request_id": request_id}
            state.update({k: v for k, v in event.items() if k != "type"})
            state["last_event"] = event["type"]
        return state


@dataclass
class SendGate:
    manifest: dict[str, str]  # tool name -> tier
    executors: dict[str, Callable[..., Any]]
    store: ApprovalStore
    audit: ApprovalStore | None = None
    _clock: Callable[[], float] = field(default=time.time)

    # -- construction -----------------------------------------------------

    @classmethod
    def from_files(
        cls,
        manifest_path: str | Path,
        executors: dict[str, Callable[..., Any]],
        store_path: str | Path,
        audit_path: str | Path | None = None,
    ) -> "SendGate":
        try:
            raw = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            manifest = {name: spec["tier"] for name, spec in raw["tools"].items()}
        except Exception as exc:  # missing/corrupt manifest -> deny all
            raise GateError(f"manifest unavailable or invalid: {exc}") from exc
        for name, tier in manifest.items():
            if tier not in TIERS:
                raise GateError(f"tool {name!r} declares unknown tier {tier!r}")
        store = ApprovalStore(Path(store_path))
        audit = ApprovalStore(Path(audit_path)) if audit_path else store
        return cls(manifest=manifest, executors=executors, store=store, audit=audit)

    # -- agent side -------------------------------------------------------

    def call(self, tool: str, **kwargs: Any) -> GateResult:
        tier = self.manifest.get(tool)
        if tier is None:
            self._audit("denied_unknown_tool", tool=tool)
            return GateResult("denied", tool, f"tool {tool!r} is not declared in the manifest")
        if tier in ("read", "draft"):
            value = self._execute(tool, kwargs)
            self._audit("executed", tool=tool, tier=tier)
            return GateResult("executed", tool, f"tier={tier}", value=value)
        # tier == send: never execute here. Record and hand back a receipt.
        request_id = uuid.uuid4().hex[:12]
        args_json = json.dumps(kwargs, ensure_ascii=False, sort_keys=True, default=str)
        event = {
            "type": "pending",
            "request_id": request_id,
            "tool": tool,
            "args": json.loads(args_json),
            "args_sha256": hashlib.sha256(args_json.encode("utf-8")).hexdigest(),
            "created_at": self._clock(),
        }
        try:
            self.store.append(event)
        except Exception as exc:
            self._audit("store_unavailable", tool=tool)
            return GateResult("denied", tool, f"approval store unavailable: {exc}")
        self._audit("blocked_pending", tool=tool, request_id=request_id)
        return GateResult(
            "pending",
            tool,
            "send blocked: recorded as a pending approval request; nothing was sent",
            request_id=request_id,
        )

    # -- human side -------------------------------------------------------

    def approve(self, request_id: str, approver: str) -> dict:
        state = self._require_pending(request_id)
        self.store.append(
            {"type": "approved", "request_id": request_id, "by": approver, "at": self._clock()}
        )
        self._audit("approved", request_id=request_id, by=approver)
        return state

    def deny(self, request_id: str, approver: str) -> dict:
        state = self._require_pending(request_id)
        self.store.append(
            {"type": "denied", "request_id": request_id, "by": approver, "at": self._clock()}
        )
        self._audit("denied", request_id=request_id, by=approver)
        return state

    def execute_approved(self, request_id: str) -> GateResult:
        try:
            state = self.store.request_state(request_id)
        except Exception as exc:
            self._audit("store_unavailable", request_id=request_id)
            return GateResult("denied", "", f"approval store unavailable: {exc}")
        if state is None:
            return GateResult("denied", "", f"no such request: {request_id}")
        tool = state.get("tool", "")
        if state.get("last_event") == "sent":
            self._audit("denied_replay", tool=tool, request_id=request_id)
            return GateResult("denied", tool, "already executed; approvals are single-use")
        if state.get("last_event") != "approved":
            return GateResult(
                "denied", tool, f"request is {state.get('last_event')}, not approved"
            )
        value = self._execute(tool, state.get("args", {}))
        self.store.append({"type": "sent", "request_id": request_id, "at": self._clock()})
        self._audit("sent", tool=tool, request_id=request_id)
        return GateResult("executed", tool, "approved send executed", request_id=request_id, value=value)

    def pending(self) -> list[dict]:
        ids: list[str] = []
        for event in self.store.events():
            rid = event.get("request_id")
            if rid and rid not in ids:
                ids.append(rid)
        states = [self.store.request_state(rid) for rid in ids]
        return [s for s in states if s and s.get("last_event") == "pending"]

    # -- internals --------------------------------------------------------

    def _require_pending(self, request_id: str) -> dict:
        try:
            state = self.store.request_state(request_id)
        except Exception as exc:
            raise GateError(f"approval store unavailable: {exc}") from exc
        if state is None:
            raise GateError(f"no such request: {request_id}")
        if state.get("last_event") != "pending":
            raise GateError(f"request {request_id} is {state.get('last_event')}, not pending")
        return state

    def _execute(self, tool: str, kwargs: dict) -> Any:
        fn = self.executors.get(tool)
        if fn is None:
            raise GateError(f"no executor registered for declared tool {tool!r}")
        return fn(**kwargs)

    def _audit(self, type_: str, **fields: Any) -> None:
        sink = self.audit or self.store
        try:
            sink.append({"type": f"audit:{type_}", "at": self._clock(), **fields})
        except Exception:
            pass  # audit failure must never turn a refusal into an execution


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="send_gate", description="Human side of the send gate")
    parser.add_argument("--store", required=True, help="path to the approval store (JSON lines)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list pending approval requests")
    for name in ("approve", "deny"):
        p = sub.add_parser(name)
        p.add_argument("request_id")
        p.add_argument("--by", required=True, help="who is deciding (recorded in the audit log)")
    args = parser.parse_args(argv)

    gate = SendGate(manifest={}, executors={}, store=ApprovalStore(Path(args.store)))
    if args.cmd == "list":
        for state in gate.pending():
            print(f"{state['request_id']}  {state['tool']}  args={json.dumps(state.get('args', {}), ensure_ascii=False)}")
        return 0
    try:
        if args.cmd == "approve":
            gate.approve(args.request_id, args.by)
            print(f"approved {args.request_id} by {args.by}")
        else:
            gate.deny(args.request_id, args.by)
            print(f"denied {args.request_id} by {args.by}")
    except GateError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
