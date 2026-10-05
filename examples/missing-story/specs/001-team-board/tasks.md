# Tasks: Team Task Board

**Input**: Design documents from `/specs/001-team-board/`

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create backend/ and frontend/ project structure per plan
- [x] T002 Initialize Fastify + Drizzle backend and React frontend
- [ ] T003 [P] Configure ESLint and Prettier

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 Set up PostgreSQL schema and migrations in backend/src/db/
- [ ] T005 [P] Implement session authentication middleware in backend/src/api/auth.ts
- [ ] T006 Implement board access check in backend/src/services/access.ts (FR-005)

---

## Phase 3: User Story 1 - Create a board and add cards (Priority: P1) 🎯 MVP

- [x] T007 [P] [US1] Create Board and Card models in backend/src/models/ (FR-001, FR-002)
- [x] T008 [US1] Implement POST /boards in backend/src/api/boards.ts (FR-001)
- [ ] T009 [US1] Implement card CRUD in backend/src/api/cards.ts (FR-002)
- [ ] T010 [US1] Build board page in frontend/src/pages/Board.tsx

---

## Phase 4: User Story 2 - Move cards between columns (Priority: P1)

- [ ] T011 [US2] Implement PATCH /cards/{id}/position in backend/src/api/cards.ts (FR-003)
- [ ] T012 [US2] Broadcast card moves over SSE in backend/src/services/events.ts
- [ ] T013 [US2] Drag and drop between columns in frontend/src/components/Column.tsx

---

## Phase 5: User Story 4 - Notifications about changes (Priority: P3)

- [ ] T014 [US4] Create Notification model in backend/src/models/notification.ts (FR-006)
- [ ] T015 [US4] Notification bell in frontend/src/components/Bell.tsx

---

## Phase N: Polish & Cross-Cutting Concerns

- [ ] T016 [P] Playwright smoke test for board flow in frontend/tests/board.spec.ts
