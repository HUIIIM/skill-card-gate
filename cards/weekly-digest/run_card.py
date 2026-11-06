"""Weekly Digest Card: the reference card, runnable end to end.

Story: a reader taps the card next to a post. The card reads the
thread (tier=read), drafts a weekly digest locally (tier=draft), then
tries to share it back to the feed (tier=send) - and is stopped by the
gate. The share becomes a pending approval request; a human approves
it out of band, and only then does the digest go out, exactly once.

Fake executors stand in for the feed so the demo runs anywhere:

    python cards/weekly-digest/run_card.py            # card runs, send blocked
    python -m gate.send_gate --store card_store.jsonl list
    python -m gate.send_gate --store card_store.jsonl approve <id> --by you
    python cards/weekly-digest/run_card.py execute <id>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gate.send_gate import SendGate  # noqa: E402

HERE = Path(__file__).resolve().parent
STORE = Path("card_store.jsonl")

THREAD = [
    "Mon: shipped the migration brief; apex domain live on the new host.",
    "Wed: contrast gate caught a footer contrast bug on mobile - fixed same day.",
    "Fri: weekly notes published; three follow-ups opened for next week.",
]


def read_thread(**kwargs):
    return THREAD


def draft_digest(**kwargs):
    lines = ["Weekly digest", ""] + [f"- {item}" for item in kwargs["items"]]
    return "\n".join(lines)


def share_to_feed(**kwargs):
    return f"SHARED to feed: {kwargs['text'].splitlines()[0]} ({len(kwargs['text'])} chars)"


EXECUTORS = {
    "feed.read_thread": read_thread,
    "digest.draft": draft_digest,
    "feed.share": share_to_feed,
}


def make_gate() -> SendGate:
    return SendGate.from_files(HERE / "permissions.json", EXECUTORS, STORE)


def main(argv: list[str]) -> int:
    gate = make_gate()
    if len(argv) == 2 and argv[0] == "execute":
        result = gate.execute_approved(argv[1])
        print(f"[{result.status}] {result.detail}")
        if result.value:
            print(f"  -> {result.value}")
        return 0
    thread = gate.call("feed.read_thread")
    print("card: reading the thread it is attached to (tier=read)")
    print(f"  -> {len(thread.value)} posts in the thread")
    digest = gate.call("digest.draft", items=thread.value)
    print("card: drafting the weekly digest locally (tier=draft)")
    print("  -> digest drafted, stays on this machine")
    share = gate.call("feed.share", text=digest.value)
    print("card: trying to share the digest to the feed (tier=send)")
    print(f"  -> [{share.status}] {share.detail}")
    if share.request_id:
        print(f"  -> approval request id: {share.request_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
