# Dependency Upgrades Stewardship Guide

Automated dependency tools (Dependabot, Renovate) submit regular pull requests to update project dependencies. As an open-source steward, your role is to keep dependencies current and secure without introducing regressions or breaking changes.

---

## 1. Triage & Identification

In `gh-beads`, dependency PRs typically carry:
- Label `author:bot` (identifying automated bots like `dependabot[bot]` or `renovate[bot]`).
- Label `type:pr`.
- Labels indicating size (`size:s`, `size:m`, `size:l`).

> [!IMPORTANT]
> Bot authorship and green CI are factual signals, **not** priority or risk decisions. Never auto-merge a PR solely because it came from a bot and passed automated tests.

---

## 2. Evaluation Checklist

When inspecting a dependency PR:

1. **Single vs. Grouped Updates:**
   - **Single updates:** Usually straightforward to assess. Check the package name, old version, and new version.
   - **Grouped updates:** May bundle multiple libraries across different ecosystems. Inspect each package included in the group independently.

2. **Semantic Versioning & Risk Tiers:**
   - **Patch (`x.y.Z`):** Bug fixes, internal refactoring. Generally low risk, but verify changelogs for unexpected regressions.
   - **Minor (`x.Y.z`):** New features, deprecations. Medium risk. Check if any deprecated APIs are in use in this codebase.
   - **Major (`X.y.z`):** Breaking changes. High risk. Requires reviewing migration guides, code adjustments, and verifying full test suites.

3. **Release Notes & Changelogs:**
   - Inspect release notes provided in the PR description.
   - Check upstream GitHub releases or CHANGELOG files if notes are incomplete.
   - Look for:
     - Minimum required language/runtime version bumps (e.g., Python 3.10 drop).
     - Renamed or removed functions/classes/modules.
     - Changed default configuration values.
     - Security advisories or CVE fixes (assess urgency).

4. **Code & Lockfile Impact:**
   - Verify that changes only touch dependency manifests (e.g., `pyproject.toml`, `package.json`) and lockfiles (`uv.lock`, `package-lock.json`).
   - If application code was also modified (e.g., automated migration script), review the diff with the same rigor as an external code contribution.

5. **Test Validation:**
   - Ensure all CI workflows pass.
   - If tests fail, determine if the failure is due to a broken test harness, an incompatibility with another package, or an actual breaking change in the dependency.

---

## 3. Decision Pathways

| Scenario | Recommended Maintainer Action |
| --- | --- |
| **Safe patch/minor update with passing CI** | Authorize merge via companion tool, specifying expected head SHA. Record action receipt. |
| **Grouped update where 1 of 5 packages has breaking changes** | Request splitting the PR (or re-running bot with excluded package). Do not merge. Record triage rationale and set next action. |
| **Major version bump requiring code refactoring** | Defer merge until a dedicated branch or task can address breaking changes. File a tracking task or link to existing issue. |
| **Failing CI due to dependency conflict** | Flag conflict to bot or maintainer team. Note the blocker in Beads (`bd dep add` if blocked by another PR/issue). |
| **Security advisory (CVE fix)** | Prioritize review. If urgent, coordinate expedited review, validation, and release. |

---

## 4. Execution & Action Receipts

When authorized to merge a dependency PR:

1. Verify the current head commit SHA on GitHub:
   ```sh
   gh pr view NUMBER --json headRefOid -q .headRefOid
   ```
2. Merge with commit SHA verification:
   ```sh
   gh pr merge NUMBER --squash --match-head-commit <HEAD_SHA>
   ```
3. Record the triage review and action receipt in Beads:
   ```sh
   uv run --locked gh-beads-triage BEAD_ID \
     --reviewer agent \
     --rationale "Verified changelog, security advisory fix, and clean test run" \
     --next-action "Merged via gh CLI"
   bd note BEAD_ID "receipt: action=merge actor=agent timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ) target=gh:owner/repo#pr:NUMBER head_sha=<HEAD_SHA> result=confirmed"
   ```
