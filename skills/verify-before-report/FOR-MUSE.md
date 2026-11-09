# For the Muse team: making "receipt is not evidence" a platform mechanism

We use Muse heavily for real state-change work: merges, sends, publishes,
account operations. `verify-before-report` is the discipline we built to stop
false completion reports. It works, but it is discipline: it holds only as
long as every agent, in every round, chooses to follow it. The proposals below
are about moving the parts that keep breaking down into the runtime and
protocol layers, where they would hold by default.

Each proposal has four parts: an evidence anchor (case numbers refer to the
evidence cases in [`SKILL.md`](SKILL.md)), the platform-level root cause, the
proposed mechanism, and how we would verify it with real tasks once it ships.
We are glad to pilot any of these and share the results.

## Summary of the evidence

| Case | Pattern | Caught by |
| --- | --- | --- |
| Case 1 | Background-task receipt fabricated a merge (SHA, comment number, CI counts) | The lead agent's independent API read-back, in the same round |
| Case 2 | Email sent with a dropped digit; recipient's version never read back | After the fact; led to a five-step email discipline |
| Case 3 | Dropdown and thumbnail screenshots reported as connected and published | A server-side check and a fresh reload |
| Case 4 | Login wall on one browser session generalized to "login failed" | Switching session surfaces, after a physical gate had already been pushed to the user |
| Case 5 | Publish with no permalink read-back; duplicate-publish risk | A human |

Two of the five were caught by people rather than by the agent stack (Case 2 and Case 5).
In a third, Case 4, a person was asked to do unnecessary physical work.

## Proposal A: Completion-claim typing

1. **Evidence anchor.** Case 1: a background task's completion receipt had
   every field a real merge would have (merge SHA, comment number, CI counts),
   and none of it was true. Case 5: a publish was reported complete with no
   pointer to the resulting post.
2. **Platform root cause.** The handoff/receipt protocol between subagents,
   background tasks, and the lead agent is free text. A state-change claim and
   its supporting evidence share the same untyped string. So the protocol
   cannot tell a claim with evidence from a claim without it, and plausible
   identifiers inside prose look just like verified ones.
3. **Proposed mechanism.** Add a structured `claims` field to the
   handoff/receipt schema. Each entry has:
   - `claim_type`, one of `merge | send | deploy | publish | delete | restore | pay`
   - `target_id`
   - `evidence_pointer`, a reference to a read-back result produced on an
     independent channel

   A claim with an empty or missing `evidence_pointer` is marked `unverified`
   by the protocol layer itself. The lead agent's context and the user-facing
   UI show that marking without depending on the worker's wording.
4. **Our verification method.** Re-run the Case 1 pattern: a background task
   that returns a merge receipt without merging. Pass if the lead agent
   receives the claim marked `unverified`. Then run seven real tasks, one per
   claim type, and check that every claim reaching the user carries either an
   `evidence_pointer` or the `unverified` marking. Target: zero unmarked
   unverified claims.

## Proposal B: Read-back primitive

1. **Evidence anchor.** Case 1: the fabrication was exposed only because the
   lead agent happened to re-read the state through an independent API. Case
   3: twice, a screenshot stood in for state that a server-side check or a
   fresh reload would have contradicted.
2. **Platform root cause.** The runtime offers action tools, but no
   first-class read-only verification surface. A read-back is whatever the
   agent improvises, often through the same tool or session that performed
   the action, so it is neither independent nor guaranteed to happen.
3. **Proposed mechanism.** Provide a first-class `read_back(claim_type,
   target_id)` primitive. It is read-only by construction, runs on a channel
   separate from the action tool's session, and returns one of
   `verified-present | verified-absent | unknown` plus the raw observation.
   In addition, subagent and background-task completion events
   automatically attach a `read_back` result for every claim in the receipt.
   The verdict then comes from the platform, not from the worker, and
   "receipt is not evidence" becomes mechanism rather than discipline.
4. **Our verification method.** Re-run the Case 1 and Case 3 patterns
   (fabricated merge receipt; UI shows selected or updated, server state
   unchanged). Pass if the attached `read_back` returns `verified-absent` in
   both, with no agent-side prompting. Then block the read-back channel and
   confirm the primitive returns `unknown`, not a guessed state.

## Proposal C: Single-surface conclusion interception

1. **Evidence anchor.** Case 4: a publish executor hit an SMS login wall in
   one browser session and concluded the account's login had failed, with
   QR-code scanning as the only option left. It pushed a physical gate to
   the user. Another session surface had stayed logged in throughout, and
   switching surfaces published successfully.
2. **Platform root cause.** The session and login layer exposes each browser
   or session surface on its own. No protocol records how many surfaces were
   checked before a session-wide conclusion was drawn. So the runtime cannot
   tell "this surface is logged out" from "this account is logged out", and
   escalations to the user go through unchecked.
3. **Proposed mechanism.** Add a `multi_surface_rechecked` protocol bit to
   session/login conclusions ("logged out", "login failed", "only manual
   verification remains") and to any escalation that asks the user for a
   physical action. The runtime will not deliver such a conclusion to the
   user until the bit is set. Setting it requires the runtime to have
   queried every session surface it holds for that account, and the
   conclusion must list the surfaces checked with their states.
4. **Our verification method.** Reproduce Case 4: one surface shows a login
   wall while a second surface for the same account stays logged in. Pass if
   the agent's "login failed" conclusion is held back, the recheck finds the
   live surface, the publish completes, and no physical-gate request reaches
   the user. Then log out all surfaces and confirm the conclusion is
   delivered with the full surface list.

## Proposal D: Audit trail

1. **Evidence anchor.** Case 2: an email was reported sent, and no record
   showed whether the recipient's version had been read back. Case 5: the
   duplicate-publish risk was found by a human with no read-back record to
   check against. In both, the user had no way to check the report except
   by redoing the work.
2. **Platform root cause.** Completion reports are rendered as plain
   assistant text. The runtime keeps no link between a reported completion
   and the verification behind it. So users cannot audit a report, and a
   report with no read-back looks the same as one with a read-back.
3. **Proposed mechanism.** Every completion report that contains a
   state-change claim automatically carries the read-back evidence triple:
   - read-back surface
   - identifier checked
   - verdict

   The triple is drawn from Proposal B's `read_back` record, not typed by
   the agent. The report UI shows the triple next to the claim, with a
   one-click "re-check" control that re-runs the same `read_back` and shows
   the fresh verdict next to the original one.
4. **Our verification method.** Run a `send` task and a `publish` task end to
   end. Pass if each completion report shows the triple, and if one-click
   re-check reproduces the verdict. Then change the target after the report
   (delete the post; recall the message where the provider supports it) and
   confirm re-check returns a different verdict from the original.

## How we would run the pilot

- We would use the seven-type task set and pass/fail criteria in
  [`SELF-TEST.md`](SELF-TEST.md) as the shared benchmark, run before and
  after each mechanism ships.
- We would report, for each mechanism: false-completion reports reaching the
  user, physical-gate requests that turned out to be unnecessary, and
  claims that reached the user unmarked.
- We would share transcripts for every FAIL cell so the team can trace it to
  a specific layer.
