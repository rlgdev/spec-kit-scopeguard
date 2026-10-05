# Implementation Plan: Team Task Board

**Branch**: `001-team-board` | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-team-board/spec.md`

## Summary

A single-page web app with a REST backend. Boards and cards live in PostgreSQL; card moves are pushed to other members over server-sent events.

## Technical Context

**Language/Version**: TypeScript 5.6 (Node.js 22)

**Primary Dependencies**: Fastify, React 19, Drizzle ORM

**Storage**: PostgreSQL 16

**Testing**: Vitest, Playwright

**Target Platform**: Linux server, evergreen browsers

**Project Type**: web application

**Performance Goals**: card move propagated to other members in < 2 s

**Constraints**: none beyond the spec

**Scale/Scope**: teams of up to 20 people, up to 500 cards per board

## Constitution Check

All gates pass; no violations to justify.

## Project Structure

```text
backend/src/{models,services,api}
frontend/src/{components,pages,services}
```

**Structure Decision**: web application (frontend + backend).

## Scope Coverage

| ID | Title | Status | Plan reference | Reason (required if deferred) |
|----|-------|--------|----------------|-------------------------------|
| US1 | Create a board and add cards (P1) | covered | data-model.md Board, Card; contracts/boards.yaml | |
| US2 | Move cards between columns (P1) | covered | contracts/cards.yaml PATCH /cards/{id}/position; SSE channel | |
| US4 | Notifications about changes (P3) | covered | data-model.md Notification; SSE channel | |
| FR-001 | Create a board with default columns | covered | contracts/boards.yaml POST /boards | |
| FR-002 | Add, edit, delete cards | covered | contracts/cards.yaml | |
| FR-003 | Move cards and persist position | covered | contracts/cards.yaml | |
| FR-005 | Restrict board access | covered | backend/src/services/access.ts | |
| FR-006 | Notify assignee | covered | data-model.md Notification | |
| FR-007 | Per-card history | deferred | | |
