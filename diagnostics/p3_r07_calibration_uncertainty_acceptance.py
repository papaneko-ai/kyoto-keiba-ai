"""R07: conservative uncertainty wrapper over existing offline P3 calibration audit."""
from math import sqrt, isfinite
from diagnostics.p3_lab_calibration_audit import audit_calibration
from diagnostics.p3_offline_model_tournament import CANDIDATES,TournamentRejected,_hash

def wilson_interval(hits,n,*,z=1.959963984540054):
    if (type(hits) is not int or type(n) is not int or n<=0 or not 0<=hits<=n or not isfinite(z) or z<=0):
        raise TournamentRejected("wilson_invalid_count")
    p=hits/n; den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    half=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,mid-half),min(1.,mid+half)]

def audit_calibration_uncertainty(train,holdout,*,plan_locked_utc,bins=5,min_holdout=30,min_occupied_bin=10):
    if (type(min_holdout) is not int or min_holdout<30 or
        type(min_occupied_bin) is not int or min_occupied_bin<10):
        raise TournamentRejected("r07_minimum_sample_policy_invalid")
    if len(holdout)<min_holdout:
        raise TournamentRejected("r07_insufficient_unused_holdout")
    existing=audit_calibration(train,holdout,plan_locked_utc=plan_locked_utc,
                               bins=bins,min_holdout=min_holdout)
    models={}
    for name in CANDIDATES:
        report=existing["calibration"][name]
        blocks=[]
        for b in report["bins"]:
            n=b["count"]
            if not n:
                blocks.append({"bin_index":b["bin_index"],"n":0,"hits":0,
                    "frequency_interval_95":None,"covered":None,"adequate":False})
                continue
            hits=sum(int(r["selected_was_winner"]) for r in report["race_receipts"]
                if min(int(r["selected_probability"]*bins),bins-1)==b["bin_index"])
            if abs(hits/n-b["empirical_frequency"])>1e-12:
                raise TournamentRejected("r07_bin_receipt_inconsistent")
            lo,hi=wilson_interval(hits,n)
            blocks.append({"bin_index":b["bin_index"],"n":n,"hits":hits,
                "frequency_interval_95":[lo,hi],
                "covered":lo<=b["mean_forecast"]<=hi,"adequate":n>=min_occupied_bin})
        if sum(b["n"] for b in blocks)!=len(holdout):
            raise TournamentRejected("r07_sample_count_inconsistent")
        populated=[b for b in blocks if b["n"]]
        baseline=existing["paired_comparison"][name]
        models[name]={"n_unused_races":len(holdout),"occupied_bins":len(populated),
            "bins_with_minimum_samples":sum(b["adequate"] for b in populated),
            "all_occupied_bins_adequate":all(b["adequate"] for b in populated),
            "top_pair_ece":report["top_pair_ece"],"proper_scores":baseline,
            "delta_log_loss_vs_pl":baseline["mean_log_loss_delta_vs_PL_BASE"],
            "delta_brier_vs_pl":baseline["mean_brier_delta_vs_PL_BASE"],
            "intervals":blocks,"confidence_intervals_are_simultaneous":False}
    body={"schema":"kyoto_r07_uncertainty_lab_acceptance.v1",
        "existing_calibration_sha256":existing["audit_sha256"],
        "plan_locked_utc":plan_locked_utc,"frozen_model_family":list(CANDIDATES),
        "train_races":len(train),"unused_holdout_races":len(holdout),
        "minimum_unused_holdout":min_holdout,"minimum_occupied_bin":min_occupied_bin,
        "models":models,"all_models_bins_adequate":all(m["all_occupied_bins_adequate"] for m in models.values()),
        "interval_type":"WILSON_95_PER_BIN_DESCRIPTIVE_NOT_SIMULTANEOUS",
        "pairwise_model_improvement_certified":False,"source_scope":"LAB_OFFLINE_ONLY",
        "jra_authenticity_verified":False,"real_world_calibration_certified":False,
        "model_auto_promotion_allowed":False,"live_paper_trade_authorized":False,
        "real_betting_authorized":False}
    return {**body,"receipt_sha256":_hash(body)}
