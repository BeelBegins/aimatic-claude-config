# Historical SZL test fragility snapshot

Archived from private agent memory on 2026-07-28. This predates SZL reinitialization and its designation as future production. It is retained for forensic history only; verify every claim before use.

---
name: project-szl-site-test-fragility
description: "Pre-existing, non-cashier-related issues found in the szl site/test suite while testing the cashier-aware POS API changes"
metadata: 
  node_type: memory
  type: project
  originSessionId: f2e99553-0a9a-4f26-9063-687bc6f8f193
---

While verifying the cashier-aware POS API changes (pos_cashier_login, start_pos_session, get_active_pos_session, get_pos_closing_summary, close_pos_session, submit_online_sale, submit_pos_refund in `aimatic/offline_pos/api.py`) against the real `szl` site, several **pre-existing** issues surfaced that are unrelated to that feature work:

1. **A real, live open POS Opening Entry exists on "Bh Phase VIII Pos Profile"** (owned by nabeelmehmood448@gmail.com, opened 2026-07-03 ~00:36). This blocks any test/flow that tries to open a new shift on that exact profile (ERPNext only allows one open Opening Entry per POS Profile at a time). This broke ~20 pre-existing tests in `TestPreviewCartFunctional`/`TestPreviewCartValidation` (untouched by the cashier work) — confirmed pre-existing, not something introduced this session.
2. **`_make_restricted_pos_profile` test helper in `test_api.py` referenced nonexistent POS Profile fields** (`territory`, `customer_group`) — POS Profile in this ERPNext version has no such fields (it has `item_groups`/`customer_groups` child tables instead). Fixed during this session to use `write_off_limit` and a `branch` accounting-dimension field instead (this site has a mandatory "Branch" accounting dimension).
3. **Closing a shift that references genuinely unrelated, already-committed POS Invoices from `pos@gmail.com`/`BH-002` dated 2026-06-26 fails** during `close_pos_session`'s `on_submit` → `consolidate_pos_invoices` → validates against an old Sales Invoice (`ACC-SINV-2026-00024`) with a rate mismatch. This only reproduces when running the full test suite via `bench run-tests`, not in isolated manual reproduction — root cause not fully isolated (suspected: ERPNext's POS Invoice consolidation logic doing more than shift-scoped matching, or leftover unconsolidated invoices from original site/test-fixture setup). Affects `TestClosePosSessionCashier.test_close_shift_supervisor_allowed`.
4. **The test fixture item (`_ITEM_CODE`, first disabled=0/is_sales_item=1 item found) has zero stock** in the POS Profile's warehouse ("Bahria Phase VIII - ST"), so any test that actually calls `.insert()`/`.submit()` on a real POS Invoice fails with "Item has no stock". Worked around by adding a `_STOCKED_ITEM_CODE` fixture (queries `tabBin` for an item with `actual_qty > 0`) for the two tests that need a real successful submission.

**How to apply:** If asked to work on this site's test suite again, don't be surprised by these — they predate and are independent of the cashier-aware POS work. Issue #3 (close_pos_session consolidation failure in full-suite runs) was never fully root-caused; if revisited, needs deeper investigation into `erpnext.accounts.doctype.pos_invoice_merge_log.pos_invoice_merge_log.consolidate_pos_invoices`. Per [[feedback-no-self-testing]], don't re-run the suite to chase this — let the user drive.
