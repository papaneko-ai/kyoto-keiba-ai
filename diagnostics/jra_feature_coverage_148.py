"""Offline completeness audit and transparent first feature store for Kyoto 2026-11-07.
Never invent missing performance rows. No model scores, forecasts or network.
"""
import json,statistics
from pathlib import Path
from datetime import date,datetime,timezone
from urllib.parse import urlsplit
from hashlib import sha256

ROOT=Path("docs/diagnostics")
EVENT_DAY=date(2026,11,7)
CUTOFF=datetime.fromisoformat("2026-11-07T00:00:00+00:00")
SOURCES=("racecard","horse_profile","race_conditions","jockey_trainer","track_weather","market_odds","training_workouts","payout_result")
FIELDS={
 "racecard":("horse_number","frame_number","horse_name","horse_profile_href","past_race_dates"),
 "horse_profile":("historical_finish","historical_distance","historical_surface","historical_going",
                  "historical_jockey","historical_carried_weight","historical_body_weight",
                  "historical_race_time","historical_field_size","historical_venue"),
 "race_conditions":("race_surface","race_distance_m","current_jockey","current_carried_weight",
                    "age_sex","race_class","current_start_time"),
 "jockey_trainer":("jockey_prior_win_rate","trainer_prior_win_rate","jockey_horse_pair_results"),
 "track_weather":("track_condition_at_cutoff","weather_at_cutoff","moisture_at_cutoff"),
 "market_odds":("quinella_live_pre_race","bracket_live_pre_race"),
 "training_workouts":("workout_time","workout_condition","workout_grade"),
 "payout_result":("official_results","payout_finalized")
}
def source_for_race(n):
 if n==7:return ROOT/"JRA_KYOTO_R7_PRERACE_FROZEN_20261106.json"
 if n in (1,6,12):return ROOT/"multirace_20261106"/f"kyoto_{n:02d}_snapshot.json"
 return ROOT/"remaining8_20261106"/f"kyoto_{n:02d}_snapshot.json"
def load(path):return json.loads(Path(path).read_text(encoding="utf8"))
def profile_for(race,num):
 return ROOT/"jra_profile_replay_20261106"/f"race_{race:02d}_horse_{num:02d}_form.json"

def first_features(rows):
 if not rows:return None
 items=rows[:3]
 values=[r["finish_percentile"] for r in items if r.get("finish_percentile") is not None]
 distance=[r["distance_m"] for r in items if type(r.get("distance_m")) is int]
 if not values or not distance:return None
 return {"prior_valid_finishes_available":len(rows),
   "recent_three_mean_finish_percentile":round(statistics.mean(values),6),
   "recent_three_mean_distance_m":round(statistics.mean(distance),2),
   "recent_three_wins":sum(r.get("finish_position")==1 for r in items),
   "recent_three_surface_counts":{k:sum(x.get("surface")==k for x in items) for k in ("芝","ダ","ダート","障")}}
def build():
 profile_report=load(ROOT/"jra_profile_replay_20261106"/"replay_report.json")
 profile_status={(x["race"],x["number"]):x for x in profile_report["items"]}
 features=[];counts=[];dates_total=0;names_with_dates=0;profile_read=0
 for race in range(1,13):
  d=load(source_for_race(race))
  if d.get("race_number")!=race or d.get("race_date")!="2026-11-07":
   raise ValueError("frozen_race_identity_mismatch")
  original_hash=d.get("source_sha256")
  if not original_hash or len(original_hash)!=64:raise ValueError("missing_source_hash")
  stamp=d.get("fetched_at_utc",d.get("captured_at_utc"))
  captured=datetime.fromisoformat(stamp.replace("Z","+00:00"))
  if captured.tzinfo is None or captured.astimezone(timezone.utc)>=CUTOFF:
   raise ValueError("racecard_future_or_uncertain")
  horses=d["runners"]
  if len(horses)!=d["runner_count"] or not horses:raise ValueError("incomplete_horse_count")
  if [x["horse_number"] for x in horses]!=list(range(1,len(horses)+1)):
   raise ValueError("horse_number_duplicate_or_missing")
  if len({x["horse_name"] for x in horses})!=len(horses):
   raise ValueError("horse_name_duplicate")
  counts.append({"race_number":race,"runners":len(horses),
                 "racecard_sha256":original_hash})
  for h in horses:
   key=(race,h["horse_number"])
   prior=h.get("prior_race_dates",h.get("past_race_dates"))
   if not isinstance(prior,list):raise ValueError("missing_prior_date_list")
   parsed_dates=[date.fromisoformat(x) for x in prior]
   if any(x>=EVENT_DAY for x in parsed_dates) or len(set(parsed_dates))!=len(parsed_dates):
    raise ValueError("future_or_duplicate_prior_dates")
   if parsed_dates!=sorted(parsed_dates,reverse=True):
    raise ValueError("non_descending_prior_dates")
   days_since=(EVENT_DAY-parsed_dates[0]).days if parsed_dates else None
   days_in_90=sum((EVENT_DAY-x).days<=90 for x in parsed_dates)
   dates_total+=len(parsed_dates)
   names_with_dates+=bool(parsed_dates)
   href=h.get("horse_profile_href","")
   u=urlsplit("https://jra.jp"+href)
   if u.hostname!="jra.jp" or u.path!="/JRADB/accessU.html" or not u.query:
    raise ValueError("unverified_profile_link")
   item={"race":"2026-11-07_KYOTO_"+str(race).zfill(2)+"R",
     "race_number":race,"horse_number":h["horse_number"],
     "horse_name":h["horse_name"],"frame_number":h["frame_number"],
     "racecard_source_sha256":original_hash,
     "racecard_captured_at_utc":captured.isoformat(),
     "profile_href":href,
     "date_only_features":{"last_observed_prior_race_days_ago":days_since,
       "date_records_visible":len(prior),"recent_90day_date_count":days_in_90},
     "performance_features":None,"profile_status":"NOT_QUERIED",
     "source_coverage":{"racecard":"CONFIRMED","horse_profile":"NOT_QUERIED",
       "race_conditions":"MISSING","jockey_trainer":"MISSING","track_weather":"MISSING",
       "market_odds":"MISSING","training_workouts":"MISSING","payout_result":"NOT_APPLICABLE_BEFORE_RACE"},
     "prediction_ready":False,"training_ready":False}
   if key in profile_status:
    p=profile_status[key]
    if p["status"]=="PARSED":
     file=profile_for(race,h["horse_number"])
     observed=load(file)
     if (observed["horse_name"]!=h["horse_name"] or
         observed["source_sha256"]!=p["original_source_sha256"]):
      raise ValueError("profile_provenance_mismatch")
     if datetime.fromisoformat(observed["fetched_at_utc"].replace("Z","+00:00"))>=CUTOFF:
      raise ValueError("profile_after_cutoff")
     for r in observed["prior_rows"]:
      if date.fromisoformat(r["date"])>=EVENT_DAY:raise ValueError("future_prior_form_row")
     item["performance_features"]=first_features(observed["prior_rows"])
     item["profile_status"]=p.get("history_status","PARSED")
     item["source_coverage"]["horse_profile"]="VERIFIED_SOURCE_ROWS"
     item["profile_source_sha256"]=p["original_source_sha256"]
     item["nonfinish_event_count"]=len(observed.get("nonfinish_rows",[]))
     profile_read+=1
    else:
     item["profile_status"]="SOURCE_RECEIPT_BLOCKED"
     item["source_coverage"]["horse_profile"]="BLOCKED_PENDING_REVIEW"
   features.append(item)
 if len(features)!=148 or dates_total!=396:raise ValueError("unexpected_regression_count")
 if len({(x["race"],x["horse_number"]) for x in features})!=148:
  raise ValueError("duplicate_output_identity")
 coverage={"schema_version":"jra_kyoto_full_day_feature_gap_audit.v1",
   "race_date":"2026-11-07","venue":"KYOTO","runner_count":148,
   "race_count":12,"prior_race_date_records":dates_total,
   "horses_with_prior_dates":names_with_dates,
   "profile_sources_queried":len(profile_status),
   "profile_sources_with_parsed_form":profile_read,
   "profile_sources_unqueried":148-len(profile_status),
   "source_status_by_group":{
     "racecard":{"status":"BASIC_ROSTER_148_VERIFIED","runners":148},
     "horse_profile":{"status":"PARTIALLY_VERIFIED","parsed":profile_read,"queried":len(profile_status)},
     "race_conditions":{"status":"NOT_STRUCTURED_OR_VERIFIED"},
     "jockey_trainer":{"status":"NOT_COLLECTED_AS_OF"},
     "track_weather":{"status":"NOT_COLLECTED_AS_OF"},
     "market_odds":{"status":"UNPUBLISHED_AT_LAST_CHECK"},
     "training_workouts":{"status":"NOT_COLLECTED_AS_OF"},
     "payout_result":{"status":"FUTURE_RESULT_MUST_NOT_BE_INPUT"}},
   "predictor_input_completeness_certified":False,
   "model_ready":False,"training_ready":False,
   "per_race":counts,"feature_catalog":FIELDS,
   "warnings":["Past-four-race dates are not full historical performance metrics.",
               "Unqueried or blocked profiles must not be imputed from future results.",
               "No odds, workouts, changing race conditions, confirmed scratches or stable horse ids."]}
 return coverage,features

def write(output):
 path=Path(output);path.mkdir(parents=True,exist_ok=True)
 summary,rows=build()
 (path/"feature_coverage.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 (path/"feature_rows_148.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 return summary
if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
 print(json.dumps(write(a.out),ensure_ascii=False))
