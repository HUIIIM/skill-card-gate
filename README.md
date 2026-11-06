<h1 align="center">skill-card-gate</h1>

<p align="center"><strong>Post the card anywhere. It still can't send without you.</strong><br/>
An open spec for feed-native skill cards - small skills that ride next to a post - where every card carries its own permission declaration and every send is physically blocked until a human approves it.</p>

<p align="center">A card runs in the feed's sandbox. The sandbox governs what may <em>run</em>; this spec governs what may <em>leave</em>. Those are different problems, and feeds only solve the first one.</p>

<p align="center">
<img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green"/>
<img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue"/>
<img alt="Dependencies: none" src="https://img.shields.io/badge/dependencies-none-brightgreen"/>
<img alt="Tests" src="https://img.shields.io/badge/tests-6%20passing-brightgreen"/>
</p>

---

A skill card is a mini-tool a creator attaches to a post: readers tap it right in the feed and it does something useful on the spot - summarizes the thread, drafts a reply, builds a digest. Useful cards eventually want to *send*: post the reply, share the digest, message the author. That is exactly where trust breaks, because a card distributed by strangers should never hold send power on its own.

So the card's manifest declares every tool it may call, each at an honest tier, and `send`-tier calls do not execute. They are recorded as pending approval requests. A human approves the exact request out of band, and only then does it run - once.

Here is the reference card doing exactly that (real output from `cards/weekly-digest/run_card.py`):

```
card: reading the thread it is attached to (tier=read)
  -> 3 posts in the thread
card: drafting the weekly digest locally (tier=draft)
  -> digest drafted, stays on this machine
card: trying to share the digest to the feed (tier=send)
  -> [pending] send blocked: recorded as a pending approval request; nothing was sent
```

The human side is three commands:

```
$ python -m gate.send_gate --store card_store.jsonl list
00540c7a4963  feed.share  args={"text": "Weekly digest\n\n- Mon: shipped the migration brief..."}

$ python -m gate.send_gate --store card_store.jsonl approve 00540c7a4963 --by you
approved 00540c7a4963 by you

$ python cards/weekly-digest/run_card.py execute 00540c7a4963
[executed] approved send executed
  -> SHARED to feed: Weekly digest (232 chars)
```

Approvals are single-use. Running the same execute again answers `[denied] already executed; approvals are single-use`.

## Quick start

```
git clone https://github.com/HUIIIM/skill-card-gate
cd skill-card-gate
python spec/validate_card.py cards/weekly-digest/card.json   # check a card against the spec
python cards/weekly-digest/run_card.py                       # watch a send get blocked
python -m pytest tests/ -q                                   # 6 tests: spec + gate promises
```

No dependencies. Python 3.10+, standard library only.

## The card manifest

Every card ships one manifest (`card.json`), checked against [`spec/skill-card.schema.json`](spec/skill-card.schema.json):

- **card** - id, name, version, author, description, entrypoint.
- **tools** - every tool the card may call, declared once, each at exactly one tier: `read` (look, fetch), `draft` (prepare, stays inside), `send` (leaves the system, or commits you in front of another person). Tier follows effect, not the tool's name.
- **gate** - `send_requires_human_approval` is normatively `true`. A card that opts out is not a conforming card, and validators reject it.
- **distribution** - how the card rides in a feed (attached to a post is the native form) and whether it runs sandboxed.

Undeclared means denied: a tool missing from the manifest gets no default tier, and a missing or invalid manifest denies everything. Validate any card with `spec/validate_card.py` before you let it near a feed.

## What's in the pack

```
spec/skill-card.schema.json       The card manifest spec (JSON Schema)
spec/validate_card.py             Dependency-free validator for the same rules
gate/send_gate.py                 The send gate (reused from HUIIIM/agent-send-gate, same author)
cards/weekly-digest/card.json     A conforming card manifest
cards/weekly-digest/permissions.json  The card's tools at honest tiers
cards/weekly-digest/run_card.py   The runnable story above, with fake executors
CHECKLIST.md                      Pre-publish self-audit for card authors and hosts
tests/test_skill_card.py          Spec and gate promises, as executable tests
```

## How it works

- The card calls tools only through the gate. `read` and `draft` pass through. `send` is converted into a pending approval request (tool, exact arguments, and a hash of them) appended to a JSON-lines store; the card receives a receipt instead of a result.
- A human reviews the queue on a surface the card cannot write to (this CLI, or a host UI over the same store) and appends an approval or a denial.
- A separate executor step runs an approved request once. The arguments that execute are the arguments that were approved; the approval is consumed by executing.
- Every step appends to an audit log the card cannot rewrite. If the store is unavailable or corrupt, sends stop. Refusal is the default in every failure mode.

## Limits

- **It only governs tools routed through it.** A card that also holds a direct posting credential can walk around the gate. The checklist covers this: cards must not hold send-capable credentials at all.
- **It is not the sandbox.** The gate governs outbound sends, not what card code may run. Hosts still sandbox execution; this spec is the missing second layer, not a replacement for the first.
- **Approval quality is on the human.** The gate guarantees a human sees the real content and destination before anything leaves. It cannot make them read it.

## Series

This is the second pack in a small series on send rights for agents. The first, [agent-send-gate](https://github.com/HUIIIM/agent-send-gate), is the general tool-layer template this gate is reused from; this pack takes the same rule into feed-native skill cards, where distribution is one tap and trust has to travel with the card.

## License

MIT. Copyright (c) 2026 Jiahui Miao. See [LICENSE](LICENSE).
