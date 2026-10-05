# scopeGuard escalation: plan gate

- **Feature**: `specs/001-invoicing`
- **Result**: unresolved after 4 of 4 resolution iterations (2026-10-05 16:24)
- **Still open**: 2 scope item(s), 0 other violation(s)
- **Artifact being resolved**: `plan.md`

The agent could not bring every scope item into the plan artifact. Each item below says what was tried, what blocks it and which decision is needed. Fix the blocker (or take the decision), then run the gate again.

## Iteration history

| Iteration | Violations | Open items |
|---|---|---|
| 0 | 2 | US3, FR-004 |
| 1 | 2 | US3, FR-004 |
| 2 | 2 | US3, FR-004 |
| 3 | 2 | US3, FR-004 |
| 4 | 2 | US3, FR-004 |

## Unresolved items

### US3 - Send invoices to customers on WhatsApp (P2)

- **Problem**: missing from plan.md 'Scope Coverage' - silently dropped from scope
- **Open since**: iteration 0
- **Spec text** (spec.md:27):

  > ### User Story 3 - Send invoices to customers on WhatsApp (Priority: P2)
  >
  > The accountant sends the invoice PDF to the customer's phone through the WhatsApp Business API.
  >
  > **Acceptance Scenarios**:
  >
  > 1. **Given** a saved invoice and a customer phone number, **When** the accountant clicks Send via WhatsApp, **Then** the customer receives the PDF in WhatsApp.

- **Attempted**:
  - Iteration 0: worked out what the plan would need (customer phone number in `data-model.md`, a WhatsApp
    delivery service in `src/services`, a `POST /invoices/{id}/whatsapp` operation in `contracts/invoices.yaml`,
    a Meta Cloud API document-message decision in `research.md`, a quickstart scenario). Every variant sends the
    customer's phone number and the invoice PDF to Meta, so no Scope Coverage row was added. Recorded the
    conflict as an open, unplanned item under Principle I in the `plan.md` Constitution Check.
  - Iteration 1: searched `spec.md`, the constitution and the rest of the project for an approved DPA or a
    deferral reason. Found none (constitution: "Approved DPAs today: none"). Looked for a self-hosted WhatsApp
    option: Meta's On-Premises API was sunset on 2025-10-23 and can no longer send messages, so only the
    Meta-hosted Cloud API remains. No plan change.
  - Iteration 2: considered a `partial` row that plans only the in-tenant parts (phone field, Send action,
    delivery log). Rejected: the acceptance outcome ("customer receives the PDF in WhatsApp") still needs Meta,
    and a partial row would pass the gate while hiding the conflict. Considered a compliant substitute channel
    (e-mail from own infrastructure, download link). Rejected because it changes the spec, which is the user's
    decision. No plan change.
  - Iteration 3: no new information (user not available during the run). Ruled out an EU-based WhatsApp
    Business Solution Provider: it is one more third party without a DPA and still delivers through Meta's
    Cloud API. No plan change.
- **Blocker**: Conflict with the constitution, Principle I "Data stays in the EU tenant" (NON-NEGOTIABLE).
  Sending invoices on WhatsApp necessarily transfers customer personal data (phone number) and invoice
  documents to Meta. Meta is not covered by an approved data-processing agreement (approved DPAs: none), and
  only a signed DPA approved by the DPO can change that. `spec.md` gives no reason to defer the story, so the
  agent may neither plan it nor defer it.
- **Decision needed**: choose one, applied to US3 and FR-004 together:
  1. **Approve Meta as a processor**: get a signed DPA with Meta (WhatsApp Business Platform / Cloud API)
     approved by the DPO, and amend `.specify/memory/constitution.md` to list it as an approved DPA. Then re-run
     `/speckit-plan` so US3 is planned as `covered`.
  2. **Defer**: state that US3 is out of scope for `001-invoicing` and give the reason, for example
     "blocked by Constitution I - no approved DPA for Meta; revisit once a DPA is signed". It is then recorded
     as `deferred` with your reason.
  3. **Change the spec**: replace WhatsApp delivery with a channel that keeps data in the EU tenant (for
     example e-mail sent from own infrastructure). Make the change via `/speckit-specify` or `/speckit-clarify`,
     then re-run `/speckit-plan`.

### FR-004 - System MUST deliver invoice PDFs to customers through the WhatsApp Business API (Meta).

- **Problem**: missing from plan.md 'Scope Coverage' - silently dropped from scope
- **Open since**: iteration 0
- **Spec text** (spec.md:42):

  > - **FR-004**: System MUST deliver invoice PDFs to customers through the WhatsApp Business API (Meta).

- **Attempted**: same as US3, which this requirement implements:
  - Iteration 0: mapped the design FR-004 needs (WhatsApp delivery service, send operation in
    `contracts/invoices.yaml`, Meta Cloud API decision in `research.md`). It requires sending invoice PDFs and
    customer phone numbers to Meta, so no row was added. Recorded the conflict under Principle I in the
    `plan.md` Constitution Check.
  - Iteration 1: no approved DPA or deferral reason anywhere in the project. No self-hosted alternative exists,
    because the WhatsApp On-Premises API was sunset on 2025-10-23 and only the Meta-hosted Cloud API remains.
    No plan change.
  - Iteration 2: rejected a `partial` row, because the requirement's core (delivery through Meta) would stay
    unplanned. Also rejected a substitute channel, because the requirement names WhatsApp / Meta explicitly and
    changing it is a spec decision. No plan change.
  - Iteration 3: no new information. Ruled out an EU WhatsApp BSP (another third party without a DPA, still
    routed through Meta). No plan change.
- **Blocker**: The requirement explicitly names a third-party service (WhatsApp Business API, Meta) that
  would receive invoice documents and customer personal data. This conflicts with constitution Principle I
  (NON-NEGOTIABLE), which allows such transfers only to services covered by an approved DPA. There are none
  today, and adding one requires a signed DPA approved by the DPO.
- **Decision needed**: the same choice as US3, kept consistent across both items:
  1. Sign and approve a DPA with Meta and add it to the constitution's approved DPAs, then re-plan, or
  2. Defer FR-004 with your stated reason, or
  3. Amend FR-004 in `spec.md` to a delivery channel that keeps data in the EU tenant, then re-plan.
