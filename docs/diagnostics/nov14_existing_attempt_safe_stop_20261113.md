# 2026-11-14 Kyoto one-shot: existing attempt / safe stop

Audit date: 2026-11-13. Repository: papaneko-ai/kyoto-keiba-ai. Diagnostic branch: jra-html-diagnostic-20261105.

Prior one-shot run 43142384975, job 130932186160, SHA fe6150757ed1d094534db5c619baac2835a3fa07, started 2026-11-12T02:34:42Z (11:34 JST). Workflow success does not indicate successful JRA capture. Job logs: NOV14_OFFICIAL_MEETING_DISCOVERY_STATUS=FAILED_CLOSED; ORIGINAL_SOURCE_BYTES_VALIDATED=False. Prior artifact 13910136436, archive digest sha256:58a7fa5003e52d69b3da6b19e0bf0c06d8b8ae7f83660811a1cbdc1861ca1b10, size 484 bytes. Receipt recorded attempted_GET=1; official_selection.html was not evidenced. Prior run 43142309331, job 130931936853 failed tests and skipped GET.

The prior run attempted GET before the prescribed 2026-11-12 16:15 JST gate. Whether JRA returned a valid original is not demonstrated. Do not claim NOT_YET_VISIBLE without source evidence.

Current code has one-shot activation trigger and offline handoff verifier. Activation file diagnostics/nov14_one_off_explicit_activation.txt returned 404 on inspection. However, prior attempted_GET=1 prevents certifying unexecuted status. DO NOT create activation file or dispatch/rerun the workflow; DO NOT fetch JRA again or guess SP/CNAME/race links. Existing source HTML, receipt, and verified handoff triple cannot be verified without official_selection.html. Racecard, quinella and bracket-market original evidence remains unverified. Maintain independent final-20 score 35/100; do not certify 40/100.

No changes to main, production Turso, public Streamlit, or live betting. Reassess only if independently preserved original evidence is located, without re-fetching.

Evidence: https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43142384975 ; https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43142309331 ; https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43142384975/artifacts/13910136436
