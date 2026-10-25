# External Code Contributions Stewardship Guide

Community contributions are essential to open-source health. Stewarding external contributions involves welcoming contributors, providing clear and constructive feedback, ensuring code quality, and smoothly shepherding pull requests from submission to merge.

---

## 1. Welcoming & Initial Assessment

When a new external PR arrives:
- **Prompt Acknowledgement:** Acknowledge the PR warmly, especially if the author is a first-time contributor (`author_association: FIRST_TIME_CONTRIBUTOR` or `FIRST_TIMER`).
- **Scope Verification:**
  - Does the PR address an existing open issue?
  - Does it align with the project roadmap and architecture?
  - If a large feature is submitted without prior discussion, politely explain that major changes require prior design consensus, but review the technical merits regardless.

---

## 2. Review Guidelines

### Constructive Tone
- Focus on the code, not the person.
- Frame suggestions with clear reasoning: "Using `collections.defaultdict` here simplifies the nested lookup" rather than "Don't do it this way."
- Provide copyable code suggestions (`suggestion` blocks) where possible to save contributor time.

### Review Focus Areas
1. **Correctness & Architecture:**
   - Does the implementation solve the intended problem?
   - Does it adhere to existing architectural patterns, abstractions, and design decisions?
   - Does it introduce unintended side effects or performance bottlenecks?
2. **Test Coverage:**
   - Are there new tests covering the change?
   - Do the tests cover edge cases (e.g., empty input, network errors, boundary values)?
   - If tests are missing, point the contributor to existing test files as examples.
3. **Documentation & Formatting:**
   - Are docstrings and type annotations updated?
   - Do linters and type checkers pass cleanly?

---

## 3. Resolving Threads & Managing Iterations

- **Review Threads:** Keep review threads open until the contributor has addressed the feedback or provided an explanation.
- **Handling Inactivity:**
  - If a contributor hasn't responded after 14 days, post a friendly check-in asking if they need help or if another maintainer can push changes to their branch.
  - Record `waiting_on: contributor` with a follow-up date in Beads.
  - Avoid closing valid PRs abruptly due to inactivity alone.

---

## 4. Pre-Merge Validation & Merge Safeguards

> [!CAUTION]
> Always re-verify the head commit SHA immediately before merging!
> If a contributor pushes a new commit while you are preparing the merge, your previous approval does not apply to the new commit.

### Pre-Merge Checklist
1. All review comments resolved.
2. All required status checks passing.
3. Base branch up to date (no merge conflicts).
4. Commits are clean and follow project commit conventions.

### Execution with Head SHA Matching
```sh
# 1. Fetch current head commit SHA
HEAD_SHA=$(gh pr view NUMBER --json headRefOid -q .headRefOid)

# 2. Re-validate locally if needed
git fetch origin pull/NUMBER/head:pr-verify
# Run verification commands...

# 3. Merge with expected head commit
gh pr merge NUMBER --squash --match-head-commit "$HEAD_SHA"

# 4. Record action receipt in Beads
bd note BEAD_ID "receipt: action=merge actor=maintainer timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ) target=gh:owner/repo#pr:NUMBER head_sha=$HEAD_SHA result=confirmed"
```

---

## 5. Post-Merge Follow-Through

1. **Thank the Contributor:** Post a brief thank-you message on the merged PR.
2. **Issue Verification:**
   - Check if the PR referenced an issue with closing keywords (e.g., `Fixes #123`).
   - If so, verify that GitHub closed the issue. If the issue remains open or only partially addressed, update the issue bead with next steps.
3. **Changelog & Milestone:** Ensure the change is added to release notes or milestone if the project tracks them.
