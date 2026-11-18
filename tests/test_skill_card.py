import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gate.send_gate import SendGate  # noqa: E402
from spec.validate_card import validate  # noqa: E402

CARD = json.loads((ROOT / "cards/weekly-digest/card.json").read_text(encoding="utf-8"))


def test_reference_card_manifest_is_valid():
    assert validate(CARD) == []


def test_card_without_human_approval_is_rejected():
    bad = json.loads(json.dumps(CARD))
    bad["gate"]["send_requires_human_approval"] = False
    assert any("send_requires_human_approval" in e for e in validate(bad))


def test_card_with_undeclared_tier_is_rejected():
    bad = json.loads(json.dumps(CARD))
    bad["tools"]["feed.share"] = {"tier": "auto"}
    assert any("tier" in e for e in validate(bad))


def _gate(tmp_path):
    return SendGate.from_files(
        ROOT / "cards/weekly-digest/permissions.json",
        {
            "feed.read_thread": lambda **kw: ["post"],
            "digest.draft": lambda **kw: "digest text",
            "feed.share": lambda **kw: "SHARED",
        },
        tmp_path / "store.jsonl",
    )


def test_card_send_is_blocked_until_approved(tmp_path):
    gate = _gate(tmp_path)
    result = gate.call("feed.share", text="digest text")
    assert result.status == "pending"
    assert gate.execute_approved(result.request_id).status == "denied"
    gate.approve(result.request_id, "reviewer")
    executed = gate.execute_approved(result.request_id)
    assert executed.status == "executed" and executed.value == "SHARED"
    assert gate.execute_approved(result.request_id).status == "denied"  # single-use


def test_card_read_and_draft_pass_through(tmp_path):
    gate = _gate(tmp_path)
    assert gate.call("feed.read_thread").status == "executed"
    assert gate.call("digest.draft").status == "executed"


def test_validator_cli_accepts_reference_card():
    out = subprocess.run(
        [sys.executable, str(ROOT / "spec/validate_card.py"),
         str(ROOT / "cards/weekly-digest/card.json")],
        capture_output=True, text=True)
    assert out.returncode == 0 and "valid: weekly-digest" in out.stdout


def _recording_gate(tmp_path):
    calls = []

    def share(**kw):
        calls.append(kw)
        return "SHARED"

    gate = SendGate.from_files(
        ROOT / "cards/weekly-digest/permissions.json",
        {
            "feed.read_thread": lambda **kw: ["post"],
            "digest.draft": lambda **kw: "digest text",
            "feed.share": share,
        },
        tmp_path / "store.jsonl",
    )
    return gate, calls


def test_approval_carries_args_hash_and_execution_verifies_it(tmp_path):
    gate, calls = _recording_gate(tmp_path)
    result = gate.call("feed.share", text="digest text")
    gate.approve(result.request_id, "reviewer")
    events = [e for e in gate.store.events() if e.get("request_id") == result.request_id]
    pending_hash = next(e["args_sha256"] for e in events if e["type"] == "pending")
    approved_hash = next(e["args_sha256"] for e in events if e["type"] == "approved")
    assert approved_hash == pending_hash
    executed = gate.execute_approved(result.request_id)
    assert executed.status == "executed"
    assert calls == [{"text": "digest text"}]


def test_args_swapped_after_approval_are_refused(tmp_path):
    # Regression for the swapped-arguments probe: a forged approval event
    # carrying different args must not change what executes.
    gate, calls = _recording_gate(tmp_path)
    result = gate.call("feed.share", text="BENIGN digest")
    gate.approve(result.request_id, "reviewer")
    gate.store.append(
        {
            "type": "approved",
            "request_id": result.request_id,
            "by": "mallory",
            "args": {"text": "MALICIOUS"},
        }
    )
    refused = gate.execute_approved(result.request_id)
    assert refused.status == "denied"
    assert calls == []
    assert any(
        e.get("type") == "audit:denied_tamper" for e in gate.store.events()
    )


def test_args_swapped_with_forged_matching_hash_are_refused(tmp_path):
    # Stronger variant: the forged event even carries a hash that matches
    # its own malicious args. The hash recorded at request time is the
    # anchor, so this is still refused.
    gate, calls = _recording_gate(tmp_path)
    result = gate.call("feed.share", text="BENIGN digest")
    gate.approve(result.request_id, "reviewer")
    malicious = {"text": "MALICIOUS"}
    forged_hash = hashlib.sha256(
        json.dumps(malicious, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    gate.store.append(
        {
            "type": "approved",
            "request_id": result.request_id,
            "by": "mallory",
            "args": malicious,
            "args_sha256": forged_hash,
        }
    )
    refused = gate.execute_approved(result.request_id)
    assert refused.status == "denied"
    assert calls == []
