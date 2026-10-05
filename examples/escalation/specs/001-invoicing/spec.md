# Feature Specification: Invoicing

**Feature Branch**: `001-invoicing`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create an invoice (Priority: P1)

An accountant creates an invoice for a customer with line items and VAT.

**Acceptance Scenarios**:

1. **Given** a customer, **When** the accountant adds two line items and saves, **Then** an invoice with a number and totals is stored.

---

### User Story 2 - Download invoice PDF (Priority: P1)

The accountant downloads the invoice as a PDF.

**Acceptance Scenarios**:

1. **Given** a saved invoice, **When** the accountant clicks Download, **Then** a PDF with all line items is downloaded.

---

### User Story 3 - Send invoices to customers on WhatsApp (Priority: P2)

The accountant sends the invoice PDF to the customer's phone through the WhatsApp Business API.

**Acceptance Scenarios**:

1. **Given** a saved invoice and a customer phone number, **When** the accountant clicks Send via WhatsApp, **Then** the customer receives the PDF in WhatsApp.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST store invoices with line items, VAT rate and totals.
- **FR-002**: System MUST number invoices sequentially per year.
- **FR-003**: System MUST render an invoice as PDF.
- **FR-004**: System MUST deliver invoice PDFs to customers through the WhatsApp Business API (Meta).
