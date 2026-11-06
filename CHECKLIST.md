# Skill card gate checklist

Self-audit for card authors and feed hosts. Every box should be checked
before a card is published or a host enables third-party cards.

## For card authors

- [ ] `card.json` validates against `spec/skill-card.schema.json`
      (`python spec/validate_card.py path/to/card.json` exits 0).
- [ ] Every tool the card can call is declared in the manifest - no
      undeclared calls, no dynamic tool discovery at runtime.
- [ ] Each tool's tier follows its effect, not its name: anything that
      transmits, posts, messages, pays, or commits the user in front of
      another person is `send`, even if it is called "reply" or "share".
- [ ] Mixed-effect tools are split, or tiered at their most dangerous
      effect.
- [ ] `gate.send_requires_human_approval` is `true` and nothing in the
      card's code paths around the gate for send-tier tools.
- [ ] The card holds **no** send-capable credentials (no posting tokens,
      no mailbox passwords). If it can send without the gate, the gate
      is decoration.
- [ ] The card degrades honestly: when a send is pending or denied, the
      user sees that state - the card never reports "shared" for a send
      that was only queued.

## For hosts / feed platforms

- [ ] Cards run sandboxed and locally; card code gets no network access
      except through declared tools routed via the gate.
- [ ] The approval surface (queue UI) is not writable by card code or by
      the agent driving the card.
- [ ] Approvals are bound to the exact request (tool + argument hash)
      and are single-use; replays are denied and logged.
- [ ] The audit log is append-only from the card's point of view, and a
      missing or corrupt store blocks sends instead of waving them
      through.
- [ ] The card's declared manifest is shown to users before install:
      what it reads, what it drafts, what it may ask to send.
- [ ] Denials are final for that request; a card that needs to retry
      must create a new request a human can re-judge on its merits.

## Red flags - do not publish / do not enable

- A manifest that declares no `send` tools while the card description
  promises posting, messaging, or sharing.
- A card that asks the user to paste an account token "for convenience".
- A host approval prompt that hides the recipient or truncates the
  content being approved.
