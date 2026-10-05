# Implementation Plan: Invoicing

**Branch**: `001-invoicing` | **Spec**: [spec.md](./spec.md)

## Summary

A single Python (FastAPI) service with PostgreSQL. Invoices are stored relationally and rendered to PDF with WeasyPrint.

## Technical Context

**Language/Version**: Python 3.12 | **Primary Dependencies**: FastAPI, SQLAlchemy, WeasyPrint | **Storage**: PostgreSQL 16

## Constitution Check

- I. Data stays in the EU tenant: PASS - no third-party services used.
- II. Simplicity: PASS - one service, PostgreSQL.

## Project Structure

```text
src/{models,services,api,pdf}
tests/{unit,integration}
```

## Scope Coverage

| ID | Title | Status | Plan reference | Reason (required if deferred) |
|----|-------|--------|----------------|-------------------------------|
| US1 | Create an invoice (P1) | covered | data-model.md Invoice, InvoiceLine; contracts/invoices.yaml | |
| US2 | Download invoice PDF (P1) | covered | src/pdf, contracts/invoices.yaml GET /invoices/{id}.pdf | |
| FR-001 | Store invoices | covered | data-model.md | |
| FR-002 | Sequential numbering | covered | data-model.md InvoiceNumberSequence | |
| FR-003 | Render PDF | covered | research.md WeasyPrint | |
