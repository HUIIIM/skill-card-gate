# Weekly Digest Card (reference implementation)

One content scenario, end to end: a card attached to a post in a feed.

- `card.json` - the card manifest, conforming to `spec/skill-card.schema.json` (validate it with `python spec/validate_card.py cards/weekly-digest/card.json`).
- `permissions.json` - the gate manifest for this card's three tools: `feed.read_thread` (read), `digest.draft` (draft), `feed.share` (send).
- `run_card.py` - the runnable story. The card reads and drafts freely; the moment it tries to share, the gate converts the call into a pending approval request and nothing leaves.

The card holds no feed credentials. The only path from "digest drafted" to "digest posted" runs through a human approval recorded in the gate's store, executed exactly once.
