# Impl30 — Nov28/29 same-day profile recovery, 2026-11-24

Purpose: resolve redundant or overbroad profile requests observed on Nov22; prioritize actual next-week acquisition, not test volume.

Evidence baseline: Nov22 159 registered runners versus 185 profile originals; old page-wide accessU selector could include non-roster links. Exact identities of the 26 excess historical originals have not been independently reconciled. Reuse the existing verified G03 roster, G04 prior-history parser, authenticated AES evidence and C12 artifact discovery.

Collector candidate 78cf939c3e4e822b842c3f10c88192d214d50a35 (PR #98); CI 45335008231 / job 138244918007 success, 581/581 tests; artifact 14893542474. Separate SP checks 45335008129, 45335008191 and 45335008119 successful. The 36-horse fixture has 35 reusable originals and one missing horse: 35 originals revalidated and one fresh mock GET; 36/36 verified. Three corrupt/wrong-name/late originals rejected and fetched again. GitHub lookup failure does not veto current acquisition. Original UTC retained. Parsed JSON newline repaired. No real JRA communication was performed in these tests.

Production candidate PR #94 updated to exact collector SHA in all three scheduled workflows and synchronized CI definition. Integration candidate before this receipt: 3262a17c4e187c7e61b5cfa5c51ef3a37f6009fb. Main remains 5d6c369c33b7e2d8e731e2ab56ba110235bb48b0 at last check.

Scope: implementation and offline proof of targeted profile reuse; not actual Nov28/29 complete history acquisition. Dynamic markets/body weight remain eligible for fresh observation. Historical 26-extra-identity reconciliation, actual complete history fields and same-day coverage across all archived slots remain unverified. Existing fixed five completion gates and 25 unresolved FMEA risk records are not promoted. No main merge, production DB, Secrets, or live authorization changes.
