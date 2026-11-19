# Implementation25 | Mechanical migration release gate and source snapshot

Date: 2026-11-19 JST.

## Root cause and immutable evidence
A 49,166-byte document-only ZIP was called a COMPLETE migration pack, even though prior normal source-containing backup was 53,262,616 bytes (a 99.9077% decrease). This is a **release integrity failure**, not an archive-compression improvement.

## Mandatory automatic safeguards
1. Use `diagnostics/kyoto_impl25_migration_release_gate.py` and the dedicated GitHub Actions workflow `kyoto-impl25-migration-release-gate.yml`. Do not call a candidate COMPLETE if this gate has not returned PASS.
2. Compare new ZIP with the **exact previous full backup bytes**; archive size must be at least 80% of previous size. Threshold is a guardrail only, not a proof of content.
3. Verify previous ZIP embedded exactly once, both ZIP CRCs, complete manifest SHA256/lengths, handoff docs, and at least 1,000 Python sources inside the nested chain. Missing source count fails closed even if archive remains large.
4. A **current** source release additionally requires a separate nested ZIP containing `source/main`, `source/development`, and `repository-all-refs.bundle`. Historical cumulative recovery alone cannot pass `--require-current-source`.
5. GitHub workflow executes 10 destructive regression cases and publishes a real ZIP only after successful current-source certification. An Actions test PASS alone does not certify an arbitrary ZIP.
6. Generate the current source/history bundle with `kyoto-impl25-current-source-snapshot.yml` after main is updated. It verifies actual main/development HEADs and manifests. Never use that snapshot alone to claim prior 53MB cumulative continuity.

## Protected work
Do not touch the 8 Nov21-22 collection slots, pinned collector SHA `ba6b62bdbb25abf5605ea3b2b2ecb7f288b1d320`, PC/SP, AES-GCM originals, experimental Turso DB, production Turso secrets or successful claim experiments.

## External dependencies
No ZIP can truthfully include remote Turso content, Github Secrets, independent Streamlit configuration, JRA live originals or expired Actions artifacts without explicit export evidence. Archive restore and full working service restore are different.

## Reset / resume
Current SHA is to be fetched on each restart. Follow the GitHub source manifest and the separate multi-source acquisition guard, not previous text claims. The 53.3MB corrected historical ZIP carries old source, but it is **not** itself a verified current-HEAD source snapshot. The corrected ZIP is labeled cumulative historical recovery until a new verified current snapshot is included and the release gate is run again.
