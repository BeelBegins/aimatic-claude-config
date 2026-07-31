# Project goals and acceptance signals

The user owns these goals. Report evidence and propose changes; do not silently
change priorities or mark a business goal complete.

## Safe production transition

Move SZL into real production only with approved scope, verified backup and
rollback, reconciled master/opening/stock/pricing totals, tested critical flows,
recorded deployment evidence, and explicit sign-off.

## Dependable retail operation

Keep the high-volume POS reliable across sale/refund, payment, shift,
offline retry/idempotency, price, receipt, FBR, stock/GL, permission, and
recovery paths. Absence of a bug report is not proof.

## Maintainable development

Keep local code as the immediate source of truth, Git as shared history, clear
module ownership, concise active risks, and coherent commits. Preserve migration
scripts and operational runbooks as executable project inputs.

## Efficient guidance

Keep the root router and each skill under 600 words, total skill bodies under
7,000 words, and routing coverage aligned exactly with the skill catalog.
Prefer one primary skill, targeted verification, current code discovery, and no
literal secrets or narrative archives.

Review these goals after cutover or a major product or operational change.
