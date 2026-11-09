# verify-before-report

**Problem:** agents report state changes (merged, sent, deployed, published, deleted, paid, restored) on the strength of receipts, screenshots, and their own summaries, so "done" often means "claimed" rather than "true".

`verify-before-report` is a Muse skill. It makes every state-change claim pass
an independent read-back and receive a three-state verdict before anyone
reports it, retries it, or calls it blocked.

## Evidence: five real failure patterns

| # | What was reported | What was actually true | Pattern |
| --- | --- | --- | --- |
| 1 | A background task's receipt showed a code merge, with merge SHA, comment number, and CI counts. | No merge had happened, the comment did not exist, and trunk was untouched. The lead agent caught it by re-reading state through an independent API in the same round. | `receipt-trusting`, `worker-said-so` |
| 2 | An email was reported as sent successfully. | A digit had been dropped from the body, turning an amount into nonsense. Nobody read back the recipient's version. A five-step email discipline followed. | `summary-as-evidence` |
| 3 | Twice, social-platform tasks reported "connected / published" from screenshots. | A dropdown showing a connection as selected had been reported as OAuth connected, but no server-side connection existed. A thumbnail had been used to report an avatar change, and a fresh reload showed it had not taken effect. | `screenshot-as-proof` |
| 4 | A publish executor said login had failed and only QR-code scanning was left, and pushed a physical gate to the user. | Another session surface had stayed logged in the whole time. Switching to it, the publish succeeded. | `single-surface generalization` |
| 5 | A content publish was reported complete without a permalink read-back. | Only a human caught the duplicate-publish risk. The publish gate now requires reading back the latest post and confirming only one exists. | `receipt-trusting` |

## The protocol

```
  state-change claim (merge / send / deploy / publish / delete / restore / pay)
                    |
                    v
  [1] DEFINE      claim type + target identifier
                    |
                    v
  [2] READ BACK   independent surface, same round
                  (receipt / screenshot / summary = NOT evidence)
                    |
                    v
  [3] VERDICT  ---------------------------------------------------
                |                    |                         |
        verified-present      verified-absent               unknown
                |                    |                         |
                v                    v                         v
  [4] ACT   report complete    one retry, same round,    stay unknown:
                               then back to [2]          name the failed read-back
                                                          and unresolved items;
                                                          no success, no failure
                |                    |                         |
                +--------------------+-------------------------+
                                     |
                                     v
  [5] REPORT  read-back surface / identifier checked / verdict
```

## Install

1. Copy the `verify-before-report/` directory into your agent's skills directory.
2. Confirm the agent lists `verify-before-report` among its available skills.
3. Run the checklist in [`SELF-TEST.md`](SELF-TEST.md) and confirm every check passes.

## How this differs from "let the agent double-check itself"

1. **Independence.** If the agent checks itself, it usually asks the same surface that produced the claim, so it reads the same receipt, the same cached page, or the same session again. This skill requires the read-back to go through a different channel and to read server-side or recipient-side state for the exact target identifier.
2. **Three-state verdicts.** A double-check gives yes or no, so a failed or ambiguous check gets rounded to one of them. This skill adds an explicit `unknown` that forbids reporting either success or failure, and it ties each verdict to a fixed action: report, retry once, or hold.
3. **Evidence carried into the report.** A double-check leaves no trace. Here, every completion report includes the read-back surface, the identifier checked, and the verdict, so a third party can re-run the check.

## Files

- [`SKILL.md`](SKILL.md): the skill, covering the protocol, claim-type table, anti-patterns, domain rules, and evidence cases.
- [`SELF-TEST.md`](SELF-TEST.md): an adopter checklist with pass/fail criteria.
- [`FOR-MUSE.md`](FOR-MUSE.md): platform-level proposals for the Muse team.
