# Kyoto AI implementation 28 — durable recovery checkpoint (2026-11-22)

## Primary goal and deadline
Preserve all November 21–22 successes and failures and prepare November 28–29 Kyoto race acquisition of ALL agreed data families. Do not spend the acquisition window redoing solved investigations. No claims of complete acquisition without per-family, per-race, per-time evidence.

## Exact GitHub evidence (not chat summaries)
- Nov22 official racecard encrypted 12R originals: Actions run 44966013490; artifact 14730699156.
- Nov22 G03 12R parsed roster/start: run 44966654858; artifact 14731603935.
- Nov22 both market official encrypted originals: run 44983969532; artifact 14738977644. ACTUAL_OFFICIAL_ODDS_MENU_RACES=12/12; ACTUAL_BOTH_MARKET_ORIGINAL_RACES=12/12; AES-GCM and SHA256 success. These are FINAL_ODDS_OR_POST_START, **NOT** proof of pre-start odds.
- Nov22 horse profile originals: run 44984067104; artifact 14739565028; previous verified count 185/185 originals. Not proof of complete historical performance parsing.
- Nov22 108-record ledger snapshot: run 44983258092; artifact 14739245461. Its UNOBSERVED entries do NOT invalidate evidence saved by independent later runs.
- Nov21 four-attempt failures plus Nov22 evidence preserved: run 44983524430; artifact 14738352793; 18 byte-identity-checked files, no JRA HTTP and no production changes.
- Nov22 result/payout menu original: run 44988118961; artifact 14740344474. Menu capture is NOT final structured results/payout proof.

## Odds parsing: DO NOT rebuild
- Prior section reported horse-quinella numeric 11/12 and bracket-quinella numeric 11/12 after image-attribute bracket-number correction. Kyoto 5R cancellation token is remaining parsing edge case. These numeric counts require replay of the exact parser receipts before release.
- Cancellation candidate classifier in diagnostics/kyoto_cancel_odds_classifier.py and tests/test_kyoto_cancel_odds_classifier.py, on branch fix/impl28-cancelled-market-cell-classifier-20261122, PR #92 DRAFT. It is NOT integrated into production odds parser and NOT merged into main.
- G03 SHA reconciliation candidate diagnostics/kyoto_impl28_evidence_reconciliation.py is a separate audit tool, not acquisition or odds parser.

## Required November 28–29 release gate
1. Locate the actual Nov22 odds parser source, image-attribute patch and 12R parser output; do not replace with a new parser. Replay original 12R, including Kyoto 5R cancelled pairs. Assert real valid cells, cancelled cells, no invented odds, and both markets independently.
2. Preserve PC primary and independently sourced SP fallback; avoid speculative SP URL. Do not let one race failure stop all 12R; record failures and continue safe alternate sources.
3. Per-race and per-family evidence for racecard, roster, horse profile, past performance, track, quinella, bracket-quinella, pre-start odds timestamps, official result and payout. Distinguish raw original, structured verified, unavailable, failed and cancellation.
4. Prove scheduled unattended start, encrypted artifact upload, shared Turso reservation/failover, retries and next-day failure-feedback repairs. Protect fixed 8 slots, secrets, main, production Turso.
5. Independent negative/regression tests and full bug audit. Only then request explicit approval for main merge. Never treat a green Actions job as proof of live data completeness.

## Restart contract
At the start of ANY new chat, read this file and current GitHub branch/PR status and Actions evidence. Never ask the user to paste stopped chat logs. Reconcile against newest immutable receipts, keep solved items solved, and continue from first incomplete gate. Record new findings as committed append-only checkpoints before conversation can end.
