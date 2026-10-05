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
