---
name: purchase-cycle
description: Use for Purchase Order, Purchase Receipt, Purchase Invoice, purchase returns, supplier pricing, purchase taxes or formulas, trade offers, landed costs, procurement grids, and purchase-related Client or Server Script fixtures.
---

# Purchase cycle

Trace the connected flow before editing:

`Purchase Order -> Purchase Receipt/return -> Purchase Invoice/return -> stock, supplier payable, tax, and pricing effects`.

## Invariants

- Make server-side validation and calculation authoritative. Client scripts may
  improve entry but must not be the only correctness control.
- Preserve document lifecycle, references, `docstatus`, received/returned
  quantities, cancellation/amendment behavior, stock reversal, GL reversal, and
  retry safety.
- Derive or validate prices, tax, supplier, company, account, and totals on the
  server. Never rely on a client-supplied accounting value.
- Keep company, branch, warehouse, cost center, supplier, and account context
  aligned. Do not introduce generic fallback warehouses or cost centers.
- Treat shelf and Foodpanda propagation as a separate owner. Use
  `shelf-pricing` only when the requested change modifies selling-price effects.

## Inspect and change

Search purchase entries in `fixtures/client_script.json`,
`fixtures/server_script.json`, Custom Field and Property Setter fixtures, plus
owned hooks and patches. Search by script name and embedded code, not only by
filename. Confirm standard ERPNext behavior before adding customization, then
change the smallest authoritative layer.

## Verify narrowly

Validate fixture JSON and extract-check edited embedded JavaScript or Python.
Exercise the affected normal document and its return/cancel counterpart; add
partial receipt/invoice, amendment, or landed-cost coverage only when the change
touches those paths. Reconcile stock, payable, and tax values when accounting is
affected. Use a disposable/local site for behavior tests and the production gate
for any site mutation.
