# Companion Tools Integration Guide

The `gh-beads` hub provides local issue and PR synchronization, portfolio-wide aggregation, deterministic triage queues, and remembered decision history. It is intentionally **read-only** toward GitHub.

To perform upstream maintainer actions (posting comments, submitting reviews, merging PRs, managing labels), maintainers pair `gh-beads` with an authorized **companion tool**, such as the GitHub CLI (`gh`) or an agent GitHub connector.

---

## 1. Authentication & Separation of Credentials

> [!IMPORTANT]
> The GitHub CLI (`gh`) and the `gh-beads` hub use independent authentication mechanisms. Running `gh auth login` configures the GitHub CLI on your system, but does **not** inject the `GH_TOKEN` environment variable required by `gh-beads`'s internal GitHubKit adapter.

- **For `gh-beads`:** Ensure `GH_TOKEN` is exported in the environment where `gh-beads sync` runs.
- **For GitHub CLI (`gh`):** Authenticate with `gh auth login` or export `GITHUB_TOKEN` / `GH_TOKEN` with write permissions.

### Capability Permissions
For full stewardship workflows using companion tools:
- **Comments & Issues:** Read & write issues and discussions.
- **Pull Requests:** Read & write pull requests, review submissions, and merge operations.
- **Organization / SAML Access:** If managing organization repositories, ensure the token is authorized for SAML Single Sign-On (SSO).

---

## 2. Standard Companion Tool Commands

### Reading Live Upstream Context
Before commenting or acting, read live conversation details when necessary:
```sh
# View full issue thread
gh issue view NUMBER --repo OWNER/REPO --comments

# View pull request review comments and conversation
gh pr view NUMBER --repo OWNER/REPO --comments
```

### Posting Comments & Information Requests
```sh
# Post comment on issue
gh issue comment NUMBER --repo OWNER/REPO --body "..."

# Post comment on pull request
gh pr comment NUMBER --repo OWNER/REPO --body "..."
```

### Submitting PR Reviews
```sh
# Submit an approval
gh pr review NUMBER --repo OWNER/REPO --approve --body "LGTM! Verified tests and documentation."

# Submit changes requested
gh pr review NUMBER --repo OWNER/REPO --request-changes --body "Please address the missing test cases noted in the review comments."

# Submit general comment
gh pr review NUMBER --repo OWNER/REPO --comment --body "Reviewed architecture; looks promising. Added suggestions inline."
```

### Safe PR Merging with Head SHA Matching
GitHub's merge endpoint supports validating that the pull request's head commit has not changed since review:
```sh
# 1. Inspect current head commit SHA
HEAD_SHA=$(gh pr view NUMBER --repo OWNER/REPO --json headRefOid -q .headRefOid)

# 2. Merge with commit match safeguard
gh pr merge NUMBER --repo OWNER/REPO --squash --match-head-commit "$HEAD_SHA"
```

---

## 3. Action Receipts & Timeout Reconciliation

Whenever an action is executed upstream via a companion tool, record an action receipt in the bead note:

### Receipt Format
```markdown
[Action Receipt]
action: <comment | review | merge | label | close>
actor: <maintainer-or-agent>
timestamp: <ISO8601 UTC>
target_url: <https://github.com/OWNER/REPO/issues/NUMBER>
head_sha: <commit-sha-if-applicable>
result: <confirmed | pending | failed>
error: <error-message-if-failed>
```

### Beads CLI Recording
```sh
bd note BEAD_ID "receipt: action=merge actor=agent timestamp=2026-10-23T06:00:00Z target=gh:owner/repo#pr:123 head_sha=abc1234 result=confirmed"
```

### Handling Ambiguous Timeouts
If a network timeout occurs while submitting a comment or merging a PR:
1. **Do not retry immediately.** Retrying blindly can result in duplicate comments or double-merge attempts.
2. Mark receipt status as `pending` or `uncertain`.
3. Check live upstream state using `gh issue view` or `gh pr view` to verify whether GitHub received and applied the request.
4. Only retry once upstream absence is confirmed.
