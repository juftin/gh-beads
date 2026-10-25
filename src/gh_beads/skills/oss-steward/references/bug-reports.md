# Bug Reports Stewardship Guide

Timely and clear triage of bug reports helps reporters feel heard, keeps issues organized, and accelerates fixes while avoiding stalled or duplicate work.

---

## 1. Initial Triage & Classification

When a bug report is imported into `gh-beads`:
1. **Check Completeness:** Does the issue contain:
   - Operating system, architecture, and language/runtime versions?
   - Steps to reproduce or a minimal reproduction repository?
   - Expected behavior vs. actual behavior?
   - Complete terminal output, error logs, or stack traces?
2. **Search for Duplicates:**
   - Check existing open and closed issues in the backlog:
     ```sh
     bd list --label "repo:OWNER/REPO,type:issue" --limit 0 --json
     ```
   - If an issue is an exact duplicate, link to the canonical issue and politely explain why it is being consolidated.

---

## 2. Requesting Missing Information

> [!TIP]
> Make requests for information specific, actionable, and polite. Explain *why* the information is needed and *how* the user can provide it.

### Example Outreach Template
```markdown
Hi @reporter, thank you for reporting this!

To help us investigate and reproduce this issue:
1. What version of the tool are you running (`tool --version`)?
2. Could you share the command invocation and full output with `--verbose` enabled?
3. What operating system and architecture are you using?

Once we have these details, we'll dive right in.
```

### Recording Response Ownership
When requesting information:
- Set `waiting_on: reporter`.
- Schedule a follow-up revisit date (e.g., 7–14 days).
- Record the decision in Beads:
  ```sh
  uv run --locked gh-beads triage BEAD_ID \
    --reviewer agent \
    --rationale "Awaiting minimal reproduction steps and verbose logs from reporter" \
    --next-action "Check for reporter response by 2026-10-30"
  ```
- Post the comment upstream via the companion tool with maintainer authorization, and record the action receipt.

---

## 3. Detecting Replies & Continuity

On subsequent synchronization passes:
- The snapshot queue `changed_since_review` surfaces items where source data (comments, state) changed since the last recorded triage.
- **Inspect Conversation Before Replying:** Read the new comments carefully. If the reporter answered your questions, advance the item:
  - Update `waiting_on: maintainer`.
  - Attempt reproduction using the provided details.
  - Never repeat a question the reporter has already answered.

---

## 4. Coordinating Bug Fix PRs

When a PR is submitted to fix the bug:
1. Establish the dependency in Beads:
   ```sh
   bd dep add <BUG_BEAD_ID> <PR_BEAD_ID>
   ```
   This ensures the bug issue depends on the PR fix. Beads will keep the bug issue blocked until the PR is merged or closed.
2. Note that `gh-beads` automatically recognizes GitHub closing references (e.g. `Fixes #45`) and links dependencies during sync.
3. **Authoritative Closure:**
   - If the PR merges, GitHub closes the issue, and `gh-beads` updates the bead status to closed on the next sync.
   - If the PR is closed **without merging**, the bug is **not fixed**. The issue remains open in Beads. Update the bug bead's next action to reassess or seek an alternative fix.
