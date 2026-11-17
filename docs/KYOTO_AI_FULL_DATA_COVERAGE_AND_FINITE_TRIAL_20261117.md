# Kyoto AI | Data acquisition coverage contract and one-pass finish criteria
Date: 2026-11-17 JST
Scope: explicit restatement of agreed P1-P8 ALG-01..13 and virtual investment requirements.
Status: REQUIREMENTS / NOT EVIDENCE OF JRA HTTP ACQUISITION.

## A. Complete feature-input inventory (not just pre-race racecards and 2 odds markets)

| Family | Required attributes | Temporal scope | Audit / intended route |
|---|---|---|---|
| Identity / schedule | meeting, race ID, R number, scheduled post, course, distance, surface, start eligibility | before race | official racecard; exact observations; race id resolution |
| Entry / horse | horse number, frame number, horse ID and name, field size, scratch/substitution | before race | official racecard; detect revised entries |
| Connections | jockey, trainer, assigned weight, horse age/sex, body weight and change where published | before race | official racecard / profiles |
| Past race history | horse past starts, placing, margins, times, last 3-5 races, prior distances/classes and dates | historically available at cutoff | historical official results and profiles; do not mix post-cutoff facts |
| Form / fitness | layoff length, changes in race distance / class, recent improvement, growth hypotheses | derived exclusively from cutoff-valid records | features, keep provenance |
| Course / pace | course and going suitability, running style, passing order and finish split, lap/pace if available | cutoff-valid history/current meeting | derive only with recorded underlying evidence |
| Training / condition | official training work, workout times, training evaluations, published stable comments where legitimately accessible | before race | OPTIONAL source availability verification; never invent |
| Track/weather | going, weather, track condition and announcements, rail/course configuration if available | timestamped before race | official pre-race updates; no forecast accepted as observation |
| Odds / markets | quinella (馬連) and bracket quinella (枠連), all available combinations, prices, current/unpublished/final flags | pre-post cutoff snapshot, time-frozen | two official markets, exact screenshot/HTML/POST source bytes |
| Market behavior | multiple pre-race quote snapshots, market opening and fluctuation if supported | before race | optional repeated snapshots; distinguish timestamps |
| Race result | confirmed finish order, starters/scratch, official quinella/bracket winner combinations and payout per 100 JPY | AFTER race | official final results; not a feature available pre-race |
| Model / validation | model version, predicted pair probability, odds EV, confidence, rank, skip/accept, virtual bet and budget, return and calibration | predictions frozen PRE race; scoring POST race | immutable-ish evidence/virtual ledger; never imply real purchases |
| Provenance and resilience | raw bytes, source URL observed independently, HTTP/request state, UTC, SHA256, source lane PC/SP, schema version, acquisition cutoff, failures | every source request | encrypted originals, atomic receipts, precise missingness states |

## B. One-pass acquisition implementation policy

1. **Do not limit the long-term collection schema to 5 fields.** The above inventory covers historical, current, market, and result data. Preserve existing source acquisition work and reuse already proven historical HTML/horse profiles instead of re-downloading for demonstration.
2. **For each source family**, record (a) officially sourced; (b) previously archived and reusable; (c) derivable only from timestamp-valid sources; (d) missing/unavailable/unverified. Capture exact URLs/bytes/date SHA and source freshness wherever legally, technically and operationally possible. No fabricated values.
3. **Nov21-22 bounded live trial**: prioritize pre-race identity, entrants, current condition, two markets, odds timestamps, original proofs and metadata. Also capture accessible historical horse/profile inputs and available conditions/training without creating speculative URLs or delaying time-critical two-market collection. Do not make an impossible all-fields guarantee a prerequisite for preserving partial raw data.
4. **Post-race branch**, distinct in time and provenance: official finish/order/payout and pre-race frozen prediction reconciliation must be included in end-to-end system validation; post-race data must never leak into pre-race features.
5. **No silent omissions**: Final closeout inventories every family with acquired / archived-reusable / derived / missing / not-public / unverified; assign source and follow-up owner. A source is not 'successful' merely because GitHub reports SUCCESS or an artifact exists.
6. **Finite experiment end**: fixed candidate Nov22 18:00 JST is a closeout checkpoint for timed acquisition opportunities, NOT proof of complete coverage. Close the *attempt* as SUCCESS / PARTIAL / FAILED / NOT_EXECUTED. Accept production-ready pre-race predictions ONLY if identity/entries + both market odds + provenance/time-frozen source validity are certified; full historical/training feature quality separately scored. Start follow-up P2-P8 using acquired evidence; any further data fetch is a separately scoped gap, not indefinite reopening.
7. **Avoid rework**: report the entire matrix before finalizing collection and compare against earlier datasets (e.g. Oct31 official finals and Nov7 148 horses/96 profile snapshots previously recorded) using actual persisted artifacts when available. Do not claim archived originals are currently accessible until inspected.
8. **External timer** is launch reliability, not source proof. Prefer minimal GitHub OAuth configuration, avoid separate accounts/tokens where possible; still require a real scheduled provider trial before claiming timing quality. Existing GitHub fallback remains in place.

## C. Facts and boundaries
- These categories restate the agreed algorithm inventory; they are *not* fresh evidence of official data availability or parsing.
- Old requirements document paths cited in handoff memories were not found on main under the exact previously reported filenames during 2026-11-17 retrieval. This register does not replace those originals if found on other branches or backup packs.
- Changing code to capture new input families requires mapping each field to an authentic documented source and proving correct timestamps / parse results; do not assume current production observer already collects every family.
