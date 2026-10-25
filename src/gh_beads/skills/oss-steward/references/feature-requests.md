# Feature Requests Stewardship Guide

Feature requests reflect community engagement and provide valuable insight into how users interact with a project. Effective stewardship balances welcoming new ideas with maintaining project focus, maintainability, and architectural coherence.

---

## 1. Clarifying Use Cases & Scope

When a feature request is imported:
1. **Understand the Underlying Need:**
   - What specific problem is the user trying to solve?
   - Is this a niche scenario or a general capability that benefits many users?
   - Can the need already be met using existing options, plugins, or workflows?
2. **Clarification Outreach:**
   - If the request proposes an implementation without explaining the problem, politely ask for the motivating real-world use case:
     ```markdown
     Hi @requester, thanks for opening this proposal!
     
     Could you provide an example of the workflow or problem you're looking to solve?
     Understanding how this fits into your day-to-day workflow will help us design the right solution.
     ```

---

## 2. Decision Framework: Accept, Defer, Decline

Every feature request deserves a deliberate, transparent decision recorded with rationale:

| Decision | Criteria | Follow-Up Action |
| --- | --- | --- |
| **Accept** | Aligns with project roadmap, high community utility, sustainable maintenance cost. | Add to milestone or epic backlog. Mark as `help wanted` or assign maintainer. Record Beads priority (e.g. `P2`). |
| **Defer** | Sound idea, but dependencies or higher-priority work must come first; or waiting for additional user interest/demand. | Explain rationale to requester. Record deferred status in Beads (`bd update BEAD_ID --add-label hub:manual-status --status deferred`). Note revisit trigger. |
| **Decline** | Out of scope for project mission, excessive architectural complexity, or conflicts with design philosophy. | Politely explain why the project cannot accept this feature, suggest alternatives (e.g. wrapper script, third-party plugin), and close respectfully. |

> [!CAUTION]
> Avoid closing feature requests solely due to age or inactivity ("stale bot" style). Stale closures alienate users. If an accepted feature remains unimplemented because of lack of bandwidth, leave it labeled appropriately or seek community contributions.

---

## 3. Recording Decisions in Beads

Record decisions with clear rationale and next steps:

```sh
# Example: Accepting a feature request
uv run --locked gh-beads triage BEAD_ID \
  --reviewer maintainer \
  --rationale "Fits roadmap for v2.0; approved in design discussion" \
  --next-action "Create tracking subtasks and milestone assignment"

bd update BEAD_ID --priority 2 --add-label category:feature --json
```

If communicating the decision upstream via the companion tool:
1. Obtain maintainer authorization for the message.
2. Post comment using companion tool (`gh issue comment`).
3. Record action receipt in a bead note (`bd note BEAD_ID "receipt: action=comment ..."`).
