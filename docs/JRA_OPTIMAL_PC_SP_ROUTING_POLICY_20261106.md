# JRA PC/SP source selection: evidence-first optimal routing policy (2026-11-06)

## Current confirmed empirical data
- The 2026-11-07 Kyoto all-12-race PC HTML capture produced 148 actual pre-race runner records.
- For Kyoto 11R, SP source 128,691 bytes vs PC source 232,708 bytes (44.7% less), 16/16 horse numbers/names match and 16/16 frame numbers match with SP merged-cell carry-forward.
- Both official variants display historical form information, but full parity of historical fields, odds, cancellations, and freshness is **not** established.
- Smaller bytes does not imply the same percentage reduction in latency; multiple direct time-to-first-byte, total download and parse measurements are needed. Mobile browser UI and server-side Streamlit collector are separate.
- Modern mobile-oriented sources may expose more useful detail than desktop: rank *per field and freshness* rather than assuming PC is comprehensive.

## Implementation
New offline decision layer `diagnostics/jra_source_router.py` and regression `tests/test_jra_source_router.py`.
This does **not** fetch JRA, change Streamlit app.py, write Turso, or automatically switch PC/SP.

### Initial conservative policy
1. Both sources must have official source identity, independently verified original bytes, dates, consistent race identity, 1-to-N unique horse numbers, names, frames and horse profile references. Any missing required field blocks that source.
2. Compare the same race with capture timestamps at most 15 minutes apart. Changing race-day information can explain differences, so disagreement or long time gaps trigger RECHECK rather than overwriting old observations.
3. PC is baseline while SP has fewer than 3 independent race checks, fewer than 5 measured latency samples per route, or under 15% median latency gain. These are initial experimental thresholds, subject to change after actual measurement.
4. Once SP meets multi-race parity, completeness, safety and time metrics, SP becomes the *preferred candidate*. The outcome remains CANDIDATE—not an automatic live switch. If PC is unavailable SP may be PROVISIONAL only with sufficient prior independent checks. Neither route is declared prediction/training-ready.
5. Field-level evaluation should independently measure starter roster, profile history, surface/distance, weight, rider, scratch/exclusion, odds publication timestamp and missingness. Prefer any source demonstrating superior information for a particular field; preserve the provenance of each field and never mix post-race observations into pre-race snapshots.
6. A source should not be requested twice when a valid and sufficiently fresh cached snapshot is available; share stable race metadata between mobile browser users and server-side collector. Apply JRA terms and conservative request rates, without bypassing restrictions.

### Empirical acceptance
2026-11-06 offline GitHub Actions Run ID 42159338094: **success**, including 16 new routing policy tests; entire branch-only offline suite 118 passed, 0 failed. This proves the decision code's specified behavior, **not** real measured SP latency improvement or end-to-end production switching.

## Next evidence
SP historical form field parity, independent scratch checks, timed PC/SP load under equivalent environments, race-day correctness and odds-source proof. Collect request and parse latency samples with race+timestamp and bytes+hash provenance; keep PC fallback. Do not optimize based on bytes alone.

## Protection
Only `jra-html-diagnostic-20261105` modified. No changes to main/app.py, Turso, existing model, actual money ledger, or live Streamlit service.
