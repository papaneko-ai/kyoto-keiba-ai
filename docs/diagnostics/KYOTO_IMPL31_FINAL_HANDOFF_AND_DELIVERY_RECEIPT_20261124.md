# 京都競馬AI開発・実装31｜2026-11-24終業・11-25再開記録

## 固定復旧点
- main 5d6c369c33b7e2d8e731e2ab56ba110235bb48b0 / development 71863f2aa20b6cba459ec365ebfb9035c06e548a unchanged.
- Collector 121afc9bba4890520fddf52605a4ecb57b58fa37 (PR #104), fixed backup branch backup/impl30-to-impl31-20261124.
- Production integration candidate abb6de3d901618517a8b85f0766c7dce6b0ac458 (PR #94), fixed backup branch backup/impl30-production-to-impl31-20261124.
- Previous recovery branch backup/impl29-to-impl30-20261124 at 3cbeb3280362dab5cbe01525b5f10e3e21c7a6a0 unchanged.
- Snapshot PR #105 run 45341868010: source/history artifact 14895444876; actual evidence artifact 14896845534. Both downloaded and verified locally, Git bundle clone/fsck and source blob verification succeeded.
- Main not merged; production candidate schedules not activated. Secrets/Turso/Streamlit settings untouched.

## 11/25 first work
Keep existing research and execution roadmap. No new project, no Codex/Work migration. Goal: actual complete pre-start acquisition for Nov28/29 Kyoto all 12 races each, not increasing test count. Actual acquisition preparation 5/8=62.5%; next milestone 6/8=75%; fixed complete gates 0/5; extra adaptation 0/5. Keep fixed display order [0,100,100,100,0,100,100,0] for successful route reuse, preflight stop prevention, odds order/timing, profiles/history, track/workout/bodyweight, results/payout, bounded next-day adaptation, main scheduled activation. P07 only bounded policy selection (not arbitrary repair or real schedule proof). Prior failure rehearsal 45340811742 proves real cross-job transfer and Sunday SP 240->360 seconds with simulated dates/JRA; full regression 601/601 run 45340811501; production integration checks 45340992082/45340992298/45340991994 succeeded.
- A1 redundant adaptation: if Saturday handoff not run, timed out, unsigned, missing artifact or API failed, bounded independent Sunday analysis from trusted failure metadata; preserve baseline when no evidence; never obstruct live acquisition.
- A2 actual scheduled-start dummy experiment without JRA HTTP; verify schedule -> handoff -> application and fallback. Respect protected main; do not mistake PR-triggered simulation for schedule execution.
- A3 evaluate actual policy effects across Sunday slots; use eligible population/time windows and source proof, not just counts. If ineffective select another prevalidated policy, revert if degradation.
- A4 extend bounded recovery beyond time budget (observed PC/SP paths, priority, item-level omissions, afternoon conditions/bodyweight). Unknown bugs diagnose/repair in isolation, verify, approve before adoption.
- A5 fault-tolerant fallback, persisted applied policy/effect/reason and recovery. These five are unimplemented additional requirements at handoff.
- Remaining P01 complete reuse of verified PC/SP/auxiliary source routes; P05 afternoon bodyweight/track workflow connection and independent workout data; P08 approved main activation. Preserve original 8 morning slots, existing Secrets/Turso, source identity/UTC/AES, 40 risks, 25 FMEA, D1-D6 and final aggregate bug check. Existing postrace 19:00/22:00 and handoff 21:00 candidates. Exact SHA and prior results checked at restart; no needless repeated work.
- Historical facts: Nov21 actual failed preflight three runs; Nov22 PC12/12, SP R1 only, all 24 market originals captured late, 159 registered vs 185 profiles; 159/159 actual original profile/history parse, 1652 historical rows, 26 non-roster links; Nov24 historical result/payout 12/12 and R5 refunds, no settlement authorization or live Nov28/29 success.

## Local delivery verification
Original predecessor 408205021 bytes SHA256 5ee3e7c89cf5bfa09abcd7d4afe2b5982cc6896a2b374a4a544c7ab1619cded5 preserved byte-identically. Legacy baseline 92232819 bytes and unchanged 05/08 checkers preserved. Final combined archive 520829840 bytes SHA256 2681690fe8a273d0f11122812e2af81c2e251802400e2bf9d67ba51b8650ca09. Legacy and extended gates PASS, ratio 1.275903 vs immediate predecessor, 4090 Git-tree files (1702 Python entries across five trees), 7 refs restored, 30 runs/29 artifacts. Reverse-order real wrapper restore and CRC checked PASS. Negative probes 8/8 reject (capacity legacy/current, missing predecessor legacy/current, instruction tamper, manifest omission, single part, duplicate part).
- KYOTO_AI_IMPL31_AUTO_RESTORE_PART_1_OF_2.zip: 260463415 bytes SHA256 d679d75d5b64c71109c83ff8733c0d029bfc0cc9cd10be1a5b54ad6489437df3
- KYOTO_AI_IMPL31_AUTO_RESTORE_PART_2_OF_2.zip: 260463415 bytes SHA256 32e282b04e08cb8327e243d1117c5912572c4086a1b73071dc7655cfab015532
- Both wrappers contain AUTO_RESTORE_IMPL31.py, exact manifest, start instructions, verifier, delivery receipt. User uploads both only. Order-independent reassembly, verify before use.
- Final checked 2026-11-24T06:44:24.720712+00:00. No claim that full local split ZIPs are stored in GitHub: GitHub holds fixed backup source refs, snapshot artifacts and handoff/verification record. External Turso DB bytes/Secrets/live settings and unlisted/expired external artifacts excluded. Preserve existing authentication and key access; do not include key values.
