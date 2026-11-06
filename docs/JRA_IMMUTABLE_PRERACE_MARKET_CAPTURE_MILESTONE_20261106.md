# 2026-11-06 JRA Kyoto odds one-shot capture and immutable evidence milestone

## Actual milestone reached
Official 2026-11-07 Kyoto 11R start verified via JRA racecard: **15:45 JST = 2026-11-07T06:45:00Z**. Therefore diagnostic source-only collection should stop at 15:35 JST (10-minute paper-trade safety cutoff), unless official start changes, in which case update only after new official evidence.

Official standard Saturday sale start is 2026-11-06 18:30 JST, not proof prices are published. At 2026-11-06 13:05 JST, actual official PC and SP menus said **weekly odds not published**.

### New assembled, source-backed path
1. **Publication gate**: before sale time, no HTTP request; after race cutoff, no HTTP request.
2. **Actual official JRA racecard**: use the already verified canonical 2026-11-07 Kyoto 11R PC/SP URLs, not guessed CNAME.
3. **Official odds action**: parse `doAction` on the just-captured official racecard, send one bounded `cname` form POST. If menu says not published, stop with `OFFICIAL_NOT_PUBLISHED`, not `CAPTURE_FAILED`.
4. **Race-specific odds**: use only market links actually present in the current official odds page. If the page is still the meeting/race selection page and no explicit race-specific links exist, stop with `OFFICIAL_MENU_NEEDS_RACE_NAVIGATION`. Do not synthesize tokens or bypass the navigation.
5. **Separate raw source receipts** for quinella / bracket-quinella, UTC timestamps measured **after** each response, original byte size, SHA-256 and verified official origin.
6. **Market parser and independently verified race identity**: derive actual prices from the same bytes, compare active runner numbers/frames, require complete appropriate pair set. Two-market validation does not imply model/prediction readiness.
7. **Immutable source-only snapshots**: write private original HTML and canonical receipt once; same bytes replay returns `ALREADY_FROZEN`, any conflicting original/receipt refuses overwrite.
8. **No production promotion**: `prediction_ready=false` and `training_ready=false` even for a validated market source. No automatic model or Turso writes.

### Verified execution
- Existing official archived 2026-10-31 Kyoto 1R real originals: 16 horses, 120 quinella odds and 36 bracket-quinella odds, both with original SHA-256, successfully replayed end-to-end in an independent local harness. Both strictly quarantined as **historical final**; no backdated pre-race assertion. Local 22 tests succeeded.
- Official GitHub branch-only regression `Kyoto offline safety unit tests`, **Run 42162288749 SUCCESS**; 20 suites, **186 tests** total.
- Pre-publication one-shot **Run 42162361864** returned `WAIT_FOR_OFFICIAL_SALES` and `request_receipts: []` — **0 JRA requests**, proving no inadvertent polling before the official sale window.
- GitHub receipt `docs/diagnostics/odds_one_shot_20261106/receipt_42162361864.json` stores the pre-publication evidence.
- New GitHub modules: `diagnostics/jra_odds_source_archive.py`, `diagnostics/jra_market_source_chain.py`, `diagnostics/jra_one_shot_market_capture.py`. Tests: `tests/test_jra_odds_source_archive.py`, `tests/test_jra_market_source_chain.py`, `tests/test_jra_one_shot_market_capture.py`.

### Current unresolved live dependency (not disguised as success)
- No genuine 2026-11-07 pre-race horse-quinella or bracket-quinella values have yet been retrieved and frozen. The last verified official state remains NOT_PUBLISHED. **The real post-publication market path cannot be certified at 13:xx JST**.
- After 18:30 JST, one explicitly triggered run on the diagnostic branch is required; workflow: `.github/workflows/jra-guarded-odds-oneshot-20261106.yml`. It is *not* presently scheduled to run automatically. It can use the unique `diagnostics/odds_post_sales_activation_20261106.txt` push trigger (not created yet) or the manual workflow control if available. If JRA displays a meeting-selection page, the code stops rather than guessing; that path must be independently verified.
- The experimental runner selection is based on frozen 2026-11-06 11R roster; it does not certify final scratches or a permanent horse ID. SP odds market matrix parsing is still not independently tested with genuine SP market originals.
- Future proof must include current official start/time changes, fresh starters and cancellation, source usage permissions, exact odds publication timestamp vs collection timestamp and truly immutable private retention. GitHub Actions source artifacts currently expire after 3 days; this alone does **not** provide long-term backtest preservation.
- Synthetic test fixtures demonstrate correctness of stop/acceptance logic only; they are not evidence that future live JRA prices exist or the live site has the exact navigation structure.
- PC/SP performance remains previously evidenced SP 17.4% median advantage for 5 representative races; not yet an odds-market comparison.

## Project protection
Only `jra-html-diagnostic-20261105` was updated. **main/app.py, production Turso, published predictive model, real betting ledger untouched.** No background or scheduled work was created.
