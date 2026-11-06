"""skill-card-gate: feed skill cards with a built-in send gate.

The gate package is reused from the sibling template HUIIIM/agent-send-gate
(same author, MIT). Cards declare their tools at read/draft/send tiers;
send-tier calls never execute without out-of-band human approval.
"""

from .send_gate import GateError, GateResult, SendGate

__all__ = ["GateError", "GateResult", "SendGate"]
