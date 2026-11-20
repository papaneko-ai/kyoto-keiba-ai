# Impl27 R08 evidence chain / 2026-11-20

- Production main baseline: `2c807afadb389f0441e74d7a25f2d8d6bfc0e353` (immutable; compare identical).
- Development branch: `fix/impl27-r08-pc-capture-boundary-20261120`.
- Latest candidate SHA: `c921bb1be2e237a8cee77c151f39e85f1c4aab67`.
- GitHub independent targeted negative gate: Run `44689947557`, SUCCESS.
- GitHub REAL job-metadata PC/SP simultaneous mock: Run `44689947605`, SUCCESS; zero JRA HTTP.
- Research reuse protection: Run `44689947569`, SUCCESS.
- Legacy production pin gate: Run `44689947611`, FAILURE (intentionally rejects removal of `needs: pc-originals-independent` / changed SP timeout). Do NOT treat this as release approval.
- Earlier independent demonstration Run `44688815437`: PC synthetic capture ended at 06:35:09Z, SP gate accepted at 06:35:10Z and SP synthetic processing passed at 06:35:10Z, before PC's mock tail ended at 06:35:29Z. JRA traffic zero.
- Fix: SP job may prepare concurrently, but SP HTTP is forbidden until authenticated GitHub run metadata confirms PC source step ended; jobs unavailable/ambiguous fail closed.
- Rate limiting: after 30s, metadata polling slows to 15s rather than polling every 4s for the whole 20-min window.
- **Blocker:** current protected production release gate only approves fully serialized old `needs` design. Require independently approved alternate release gate with equivalent non-overlap assurance, observed GitHub concurrent-job behavior, and rollback receipts.
- **Do not merge or swap pinned weekend SHA**. R08 remains OPEN until preapproved protected release and live timing proof.
- Next: expose a second mode in the protected gate with strict proof of completed PC source step + no network after source step, and show same risk / incident lifecycle contract passes; cannot lower the existing gate to a status-only check.
