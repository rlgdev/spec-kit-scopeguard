# Examples

## missing-story

`specs/001-team-board` reproduces the problem scopeGuard was built for: the spec has four user
stories, but the generated `plan.md` leaves out **User Story 3 - Share a board with teammates**
(and its requirement FR-004), and defers FR-007 without saying why. The tasks follow the plan,
so the story is silently missing everywhere downstream.

```bash
cd examples/missing-story
bash ../../scripts/bash/scopeguard.sh plan      # FAIL: US3, FR-004 missing; FR-007 deferred without a reason
bash ../../scripts/bash/scopeguard.sh tasks     # FAIL: no task carries US3 / FR-004
bash ../../scripts/bash/scopeguard.sh report    # coverage matrix across plan / tasks / implement
```

## escalation

`specs/001-invoicing` contains a story that cannot be planned. User Story 3 and FR-004 require
sending invoices through the WhatsApp Business API (Meta). The project constitution
(`.specify/memory/constitution.md`) forbids sending customer data to any third party without an
approved data-processing agreement, and none exists.

In the plan gate's resolution loop the agent does not defer the story on its own and does not plan
a constitution violation. It leaves the items open. After the 4th iteration the gate exits `3`,
and the agent completes the problem report. [`sample-output/escalation-report-plan.md`](escalation/sample-output/escalation-report-plan.md)
is the report an agent produced on this example: what it tried, the blocker, and the decision
needed (approve a DPA, defer with a reason, or change the spec).

```bash
cd examples/escalation
bash ../../scripts/bash/scopeguard.sh plan --iteration 4   # exit 3, writes specs/001-invoicing/scopeguard-escalation-plan.md
```
