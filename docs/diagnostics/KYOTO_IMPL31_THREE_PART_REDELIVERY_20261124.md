# Impl31 three-part redelivery, 2026-11-24
Supersedes only the two-part transport in commit 5b65f1996d827c70a466c02dba4a33902a3a53d7. The user reported inability to download. First two-part ZIP was observed at 255639552 bytes instead of 260463415; ZIP open failed. Exact cause of truncation not established. Repackage directly from preserved verified combined archive, not damaged wrapper.

Combined archive unchanged: 520829840 bytes, SHA256 2681690fe8a273d0f11122812e2af81c2e251802400e2bf9d67ba51b8650ca09.
New delivery wrappers:
- KYOTO_AI_IMPL31_AUTO_RESTORE_PART_1_OF_3.zip 173660324 bytes SHA256 7c79eccc42c4295f2106bb876fca8bab619a76bc5d887b8949c30ab5212bb308
- KYOTO_AI_IMPL31_AUTO_RESTORE_PART_2_OF_3.zip 173660324 bytes SHA256 ef86f0a720d9eb58b1c88b780df55d16858b460875f06aa9da8614d580d2e90f
- KYOTO_AI_IMPL31_AUTO_RESTORE_PART_3_OF_3.zip 173660323 bytes SHA256 714672b21b9b5b9e729a1a4f366e77b207f7b8d4664e537b1bb5314f11364e5a

Actual three-part automatic restoration in order 3,1,2 PASS; all three ZIP CRC PASS; exact combined SHA and byte count PASS; unchanged legacy 05/08 delivery gate and extended 09 gate PASS. 4090 source files, 1702 Python files, 7 restored refs, 30 run records and 29 artifacts. Missing, duplicate and mixed old/new transport rejected 3/3. Existing six archive negative probes preserved. Verified at 2026-11-24T06:53:12.872086+00:00.

Use all three ZIPs only; do not mix with old two-part wrappers. The external three-part restoration script, manifest and amended external instructions take precedence over transport-only two-part instructions embedded in the immutable complete archive. All development facts, 62.5% preparation, next milestone 75%, five additional adaptation tasks 0/5, exact collector and deployment candidate refs and external backup exclusions remain unchanged. Source/history and evidence backup run 45341868010 remains valid. No main, production settings or previous recovery modifications; local wrapper ZIPs not uploaded to GitHub, only the redelivery record.
