# Data model

## Invoice
- id, number, customer_id, issued_on, vat_rate, net_total, gross_total

## InvoiceLine
- id, invoice_id, description, quantity, unit_price

## InvoiceNumberSequence
- year, last_number
