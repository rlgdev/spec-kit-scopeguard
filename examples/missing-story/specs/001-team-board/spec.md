# Feature Specification: Team Task Board

**Feature Branch**: `001-team-board`

**Created**: 2026-10-05

**Status**: Draft

**Input**: User description: "A lightweight task board for small teams: create boards, add and move cards, share a board with teammates, get notified about changes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create a board and add cards (Priority: P1)

A team lead creates a board with the default columns To do, Doing and Done and adds cards with a title and an optional description.

**Why this priority**: Without boards and cards there is no product.

**Independent Test**: Create a board, add three cards, reload the page and see the same cards.

**Acceptance Scenarios**:

1. **Given** no boards exist, **When** the user creates "Sprint 12", **Then** an empty board with three default columns is shown.
2. **Given** a board exists, **When** the user adds a card "Write release notes", **Then** the card appears in To do.

---

### User Story 2 - Move cards between columns (Priority: P1)

Any member drags a card to another column to show progress.

**Why this priority**: Progress tracking is the core value of a board.

**Independent Test**: Move a card from To do to Done and reload; the card stays in Done.

**Acceptance Scenarios**:

1. **Given** a card in To do, **When** the user drags it to Doing, **Then** it is shown in Doing for every member.

---

### User Story 3 - Share a board with teammates (Priority: P2)

The board owner invites teammates by e-mail; invited people can view and edit the board.

**Why this priority**: Boards are for teams; sharing is needed before the second user arrives.

**Independent Test**: Invite a second account and open the board as that account.

**Acceptance Scenarios**:

1. **Given** an owner and a registered teammate, **When** the owner invites the teammate, **Then** the teammate sees the board in their board list.
2. **Given** an invited teammate, **When** the owner removes them, **Then** the board disappears from their list.

---

### User Story 4 - Notifications about changes (Priority: P3)

Members get an in-app notification when a card assigned to them is moved or edited.

**Why this priority**: Useful, but the board works without it.

**Independent Test**: Assign a card to account B, move it as account A, see a notification as account B.

**Acceptance Scenarios**:

1. **Given** a card assigned to B, **When** A moves it, **Then** B sees one unread notification.

---

### Edge Cases

- What happens when two members move the same card at the same time? Last write wins and both see the final column.
- How does the system handle an invitation to an e-mail without an account? The invitation stays pending for 14 days.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let a signed-in user create a board with the columns To do, Doing and Done.
- **FR-002**: System MUST let board members add, edit and delete cards with a title (max 120 characters) and an optional description.
- **FR-003**: System MUST let board members move cards between columns and persist the new position.
- **FR-004**: System MUST let the board owner invite teammates by e-mail and revoke access.
- **FR-005**: System MUST restrict board access to the owner and invited members.
- **FR-006**: System MUST notify a card's assignee in-app when that card is moved or edited.
- **FR-007**: System MUST keep a per-card history of column changes.

### Key Entities

- **Board**: name, owner, members, columns.
- **Card**: title, description, column, position, assignee.
- **Invitation**: board, e-mail, status, expiry.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can create a board and add the first card in under 1 minute.
- **SC-002**: Card moves are visible to other members within 2 seconds.

## Assumptions

- Users already have accounts; sign-up is out of scope.
