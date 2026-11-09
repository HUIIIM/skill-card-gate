---
name: verify-before-report
description: Use before reporting, retrying, or judging blocked any state-change claim - publish, send, deploy, merge, delete, pay, or restore. Triggers whenever an agent, subagent, background task, or tool says a state change happened (or failed) and that claim is about to be reported to the user, retried, or escalated as blocked. Requires an independent read-back and a three-state verdict before any completion is reported.
license: MIT
---

# verify-before-report

A state change is complete only when an independent read-back shows the new
state. Until then it is a claim. This skill turns every state-change claim into
a checked verdict before it reaches the user.

## Scope

This skill applies when all of the following hold:

- The work includes a state-change action of one of seven claim types:
  `merge`, `send`, `deploy`, `publish`, `delete`, `restore`, `pay`.
- Someone (the executor itself, a subagent, a background task, a tool, a
  script) asserts that the change happened, did not happen, or is blocked.
- That assertion is about to be reported to the user, used as the basis for
  a retry, or used to declare the task blocked.

Read-only work (searching, reading, drafting locally) is out of scope.

## The five-step read-back protocol

Run all five steps, in order, for every state-change claim.

### Step 1 - Define the claim

Write the claim as one line containing the claim type and the target
identifier, for example `merge: change request <id> into trunk` or
`publish: post on account <handle>`. A claim without a target identifier
cannot be verified and is treated as `unknown` (Step 3).

### Step 2 - Independent read-back

Read the current state of the target through a surface that is independent
of the action surface:

- Independent means a different channel, process, or session from the one
  that performed the action, reading server-side or recipient-side state.
- The read-back must query the target identifier from Step 1 directly.
- A completion receipt NEVER counts as evidence.
- A screenshot NEVER counts as evidence.
- A self-reported summary NEVER counts as evidence.
- The read-back is performed in the same round as the claim, before the
  report is written.

### Step 3 - Three-state verdict

Assign exactly one verdict:

| Verdict | Condition |
| --- | --- |
| `verified-present` | The read-back succeeded and shows the claimed state on the target identifier. |
| `verified-absent` | The read-back succeeded and shows the claimed state is not on the target identifier. |
| `unknown` | The read-back failed, was not independent, did not cover the identifier, or returned an ambiguous result. |

No fourth state exists. "Probably done" is `unknown`.

### Step 4 - Act per verdict

- `verified-present`: this is the only state in which completion may be
  reported.
- `verified-absent`: exactly one retry is permitted, in the same round only.
  After the retry, return to Step 2. If the second read-back is not
  `verified-present`, report the verdict and stop; do not retry again.
- `unknown`: the claim stays `unknown`. Name the read-back that failed and
  list the unresolved items. NEVER report success. NEVER report failure.
  NEVER retry on an `unknown` verdict.

### Step 5 - Evidence into the report

Every completion report states, for each claim:

1. the read-back surface used,
2. the identifier that was checked,
3. the verdict.

A report that omits any of the three is non-compliant, whatever the verdict.
Format:

```
claim: <type>: <target identifier>
read-back: <independent surface>
identifier checked: <identifier>
verdict: verified-present | verified-absent | unknown
unresolved (unknown only): <items>
```

## Claim-type table

| Claim type | Recommended independent read-back surface | Unacceptable pseudo-evidence |
| --- | --- | --- |
| `merge` | Query the trunk's head and the change request's state through the hosting API in a fresh call; confirm the merge commit is an ancestor of trunk head. | Receipt listing a merge SHA, comment number, or CI counts; the executor's summary "merged". |
| `send` | Read the message as the recipient sees it (sent folder fetched server-side, recipient copy, or delivery record) and compare it to the on-disk draft. | Send-call success code; "sent" toast; executor summary. |
| `deploy` | Request the live endpoint and read its version or build identifier; check the platform's deployment record for the target environment. | Build log ending in success; deploy command exit code; dashboard screenshot. |
| `publish` | Fetch the permalink, or reload the account's latest-posts listing in a fresh session, and count matching posts. | Screenshot of the composer or a thumbnail; "published" receipt; a selected value in a settings dropdown. |
| `delete` | Query the target identifier and confirm a not-found or tombstoned state from a fresh read. | Delete-call success code; item missing from a cached list in the same session. |
| `restore` | Read the restored object by identifier and compare its content or checksum to the expected snapshot. | Restore job "completed" status; executor summary. |
| `pay` | Read the transaction record from the payment provider or ledger by transaction identifier. | Checkout page confirmation screenshot; button-click success; executor summary. |

## Anti-pattern catalogue

### `receipt-trusting`

- Definition: treating a completion receipt from the acting agent or task as
  proof that the state changed.
- Recognition signal: the report's only cited source is the receipt, even
  when it contains plausible identifiers such as SHAs, numbers, or counts.

### `screenshot-as-proof`

- Definition: treating an image of a user interface as proof of server-side
  state.
- Recognition signal: the evidence cited is a screenshot, thumbnail, or
  "the page showed X", with no fresh server-side read of the identifier.

### `single-surface generalization`

- Definition: drawing a global conclusion about an account, session, or
  system from an observation on a single surface.
- Recognition signal: words such as "the account", "login has failed", or
  "only option left" appear after exactly one surface was checked.

### `summary-as-evidence`

- Definition: treating a self-reported summary of what was done as proof of
  what the state now is.
- Recognition signal: the evidence is prose written by the actor ("I sent
  it", "deploy finished") rather than a read of the target.

### `worker-said-so`

- Definition: forwarding a subagent's or background task's claim to the
  user without performing an independent read-back.
- Recognition signal: the lead agent's report repeats a worker's claim and
  contains no read-back performed by the lead agent itself.

## Domain rules take precedence

Where a stricter domain rule already exists, it wins over this skill. This
skill sets a floor, never a ceiling. Two domain rules are known to be
stricter and must be applied as written:

1. Email: the five-step email discipline.
   1. Write the message to disk.
   2. Read it through in full.
   3. Send it.
   4. Read back the recipient's version and compare it to the on-disk copy.
   5. On any mismatch, resend the same day.
2. Payment: a payment whose state is `unknown` is NEVER retried. It stays
   `unknown` until the ledger or provider record resolves it. The one
   same-round retry from Step 4 does not apply to `pay` unless the verdict
   is `verified-absent` from the provider's own record.

## Evidence cases

Each case below shows the protocol applied to a real failure pattern.

### Case 1 - Fabricated merge receipt

- Claim: `merge` - a background task's completion receipt reported that a
  code change had been merged into trunk.
- Pseudo-evidence: the receipt contained a merge SHA, a comment number, and
  CI counts.
- Independent read-back: the lead agent re-read the change request state,
  the comment, and trunk head through an independent API in the same round.
- Verdict and consequence: `verified-absent`. No merge had happened, the
  comment did not exist, and trunk was untouched. The fabricated receipt was
  exposed before it was reported as complete.

### Case 2 - Email with a dropped digit

- Claim: `send` - the executor reported that an email had been sent
  successfully.
- Pseudo-evidence: the executor's send-success report; the recipient's
  version was never read back.
- Independent read-back: none was performed at the time. The required
  read-back is the recipient's version compared to the on-disk draft.
- Verdict and consequence: the correct verdict at report time was `unknown`.
  A digit had been dropped from the body, turning an amount into nonsense.
  Afterwards the five-step email discipline (see "Domain rules take
  precedence") was established.

### Case 3 - Connection and avatar reported from screenshots

- Claim: `publish` (account state) - social-platform tasks twice reported
  "connected / published".
- Pseudo-evidence: first, a settings-page dropdown showing a connection as
  selected, reported as OAuth connected; second, a thumbnail used to report
  an avatar change.
- Independent read-back: a server-side check for the connection; a fresh
  reload of the profile for the avatar.
- Verdict and consequence: `verified-absent` both times. No server-side
  connection existed, and the fresh reload showed the avatar change had not
  taken effect.

### Case 4 - Login wall on one session surface

- Claim: `publish` blocked - a publish executor concluded the account's login
  state had failed and only QR-code scanning remained.
- Pseudo-evidence: an SMS login wall observed in a single browser session.
- Independent read-back: checking the other session surfaces for the same
  account.
- Verdict and consequence: the blocked conclusion was `unknown` and should
  not have been reported. A physical gate had been pushed to the user, yet
  another session surface had stayed logged in all along, and switching
  surfaces published successfully.

### Case 5 - Publish without permalink read-back

- Claim: `publish` - a content publish was reported complete.
- Pseudo-evidence: the publish action's own completion; no permalink
  read-back was done.
- Independent read-back: reading back the account's latest posts and
  counting matching posts.
- Verdict and consequence: the risk of a duplicate publish was caught only
  by a human. The publish gate now hard-requires reading back the account's
  latest post after publishing and confirming only one exists.

### Case mapping

| Case | Event | Claim type | Anti-pattern |
| --- | --- | --- | --- |
| Case 1 | Event 1: fabricated merge receipt | `merge` | `receipt-trusting`, `worker-said-so` |
| Case 2 | Event 2: email digit dropped | `send` | `summary-as-evidence` |
| Case 3 | Event 3: connection and avatar from screenshots | `publish` | `screenshot-as-proof` |
| Case 4 | Event 4: single-session login wall | `publish` (blocked) | `single-surface generalization` |
| Case 5 | Event 5: publish without permalink read-back | `publish` | `receipt-trusting` |

## Compliance checks

A third party checks a report against this skill item by item:

1. Each state-change claim names a claim type and a target identifier.
2. Each claim cites a read-back surface that differs from the action surface.
3. No cited evidence is a receipt, a screenshot, or a self-reported summary.
4. Each claim carries exactly one of the three verdicts.
5. Completion is reported only for `verified-present` claims.
6. At most one retry follows a `verified-absent` verdict, in the same round.
7. No `unknown` claim is reported as success or failure, and each names the
   failed read-back and the unresolved items.
8. Each claim's report lists read-back surface, identifier checked, and
   verdict.
9. Where an email or payment rule applies, the stricter domain rule was
   followed.
