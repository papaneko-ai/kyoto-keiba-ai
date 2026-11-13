"""One-time bounded PC/SP representative-race benchmark; never production-adopt.
Official racecard links read from archived JRA navigation, not generated.
"""
from __future__ import annotations
import argparse,hashlib,json,re,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import urlopen,Request
from urllib.parse import urlsplit
from statistics import median
from bs4 import BeautifulSoup
from diagnostics.jra_multi_capture_20261106 import parse as pc_parse

RACES=(1,5,6,11,12)  # small, maiden/newcomer, 16/17 runners
PC_NAV=Path('docs/diagnostics/JRA_LIVE_NAV_DISCOVERY_20261106.json')
SP_NAV=Path('docs/diagnostics/JRA_SP_NAV_LINKS_20261106.json')
ROOT=Path('docs/diagnostics')
UA_SP="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
UA_PC="Mozilla/5.0"
BYTES_LIMIT=1_000_000

def pc_urls(nav):
  result={}
  for x in nav['links']:
    href=x.get('href','')
    m=re.fullmatch(r"/JRADB/accessD.html\?CNAME=(pw01dde010820260501)(\d{2})(20261107)/([0-9A-Z]{2})",href)
    if m:
      n=int(m.group(2))
      result[n]="https://jra.jp"+href.replace("/"+m.group(4),"%2F"+m.group(4))
  if set(result)!=set(range(1,13)):raise ValueError("unverified_pc_nav")
  return result

def frozen(n):
  if n==7:path=ROOT/'JRA_KYOTO_R7_PRERACE_FROZEN_20261106.json'
  elif n in (1,6,12):path=ROOT/'multirace_20261106'/f'kyoto_{n:02d}_snapshot.json'
  else:path=ROOT/'remaining8_20261106'/f'kyoto_{n:02d}_snapshot.json'
  return json.loads(path.read_text(encoding='utf8'))

def fetch_once(channel,url,opener=urlopen,clock=time.perf_counter):
  host='jra.jp' if channel=='PC' else 'sp.jra.jp'
  u=urlsplit(url)
  if u.scheme!='https' or u.hostname!=host or u.path!='/JRADB/accessD.html':
    raise ValueError('invalid_official_source')
  req=Request(url,headers={'User-Agent':UA_PC if channel=='PC' else UA_SP,
                          'Accept':'text/html'},method='GET')
  start=clock()
  with opener(req,timeout=20) as resp:
    code=resp.status; final=urlsplit(resp.geturl())
    content_type=resp.headers.get('Content-Type','')
    raw=resp.read(BYTES_LIMIT+1)
  elapsed=(clock()-start)*1000
  if (code!=200 or final.scheme!='https' or final.hostname not in
    (('jra.jp','www.jra.go.jp') if channel=='PC' else ('sp.jra.jp','app.jra.jp'))
    or not 0<len(raw)<=BYTES_LIMIT or 'html' not in content_type.lower()):
    raise ValueError('invalid_response')
  return raw,round(elapsed,2)

def sp_rows(raw):
  soup=BeautifulSoup(raw.decode('cp932',errors='replace'),'html.parser')
  tables=soup.select('table')
  if not tables:raise ValueError('sp_missing_table')
  output=[]
  frame=None
  for tr in tables[0].select('tr'):
    # A true entrant is a row with one SP profile anchor and .uban number.
    anchors=tr.select('a[href*="/JRADB/accessU.html"]')
    numbers=tr.select('.uban')
    if len(anchors)!=1 or len(numbers)!=1:continue
    number_text=numbers[0].get_text(' ',strip=True)
    if not number_text.isascii() or not number_text.isdigit():raise ValueError('bad_sp_number')
    n=int(number_text)
    if not 1<=n<=18:raise ValueError('sp_number_out_of_range')
    slot=tr.select_one('.wban')
    if slot:
      raw_frame=slot.get_text(' ',strip=True)
      if raw_frame:
        if not raw_frame.isascii() or not raw_frame.isdigit() or not 1<=int(raw_frame)<=8:
          raise ValueError('bad_sp_frame')
        frame=int(raw_frame)
    if frame is None:raise ValueError('missing_initial_sp_frame')
    name=anchors[0].get_text(' ',strip=True)
    if not name:raise ValueError('empty_sp_name')
    output.append((n,frame,name))
  nums=[x[0] for x in output]
  if not output or nums!=list(range(1,len(output)+1)):raise ValueError('incomplete_mobile_roster')
  if len(output)!=len(set(output)):raise ValueError('duplicate_mobile_roster')
  return tuple(output)

def pc_rows(raw,race,*,meeting_date='2026-11-07'):
  runners,errors=pc_parse(raw,race,meeting_date=meeting_date)
  if errors:raise ValueError('pc_parser_errors:'+','.join(errors))
  return tuple((x['horse_number'],x['frame_number'],x['horse_name']) for x in runners)

def benchmark(out):
  directory=Path(out);directory.mkdir(parents=True,exist_ok=True)
  pc=pc_urls(json.loads(PC_NAV.read_text(encoding='utf8')))
  sp={int(k):v for k,v in json.loads(SP_NAV.read_text(encoding='utf8'))['official_race_links'].items()}
  if set(sp)!=set(range(1,13)):raise ValueError('SP navigation incomplete')
  cutoff=datetime.fromisoformat('2026-11-07T01:05:00+00:00')
  if datetime.now(timezone.utc)>=cutoff:raise ValueError('race_started')
  receipts=[]
  for idx,n in enumerate(RACES):
    # Alternate order to reduce systematic first-request/cache advantage.
    sequence=('PC','SP') if idx%2==0 else ('SP','PC')
    observations={}
    for channel in sequence:
      if receipts or observations:time.sleep(1)
      rec={'channel':channel,'race':n,'source_url':pc[n] if channel=='PC' else sp[n],
           'recorded_at_utc':datetime.now(timezone.utc).isoformat(),
           'status':'STARTED','network_ms':None,'parse_ms':None,
           'prediction_ready':False,'training_ready':False}
      try:
        if datetime.now(timezone.utc)>=cutoff:raise ValueError('race_cutoff')
        raw,elapsed=fetch_once(channel,rec['source_url'])
        start=time.perf_counter()
        rows=pc_rows(raw,n) if channel=='PC' else sp_rows(raw)
        parse_ms=round((time.perf_counter()-start)*1000,2)
        rec.update(status='PARSED',source_sha256=hashlib.sha256(raw).hexdigest(),
            raw_bytes=len(raw),network_ms=elapsed,parse_ms=parse_ms,
            rows=len(rows),roster=rows)
        (directory/f'race_{n:02d}_{channel.lower()}.html').write_bytes(raw)
      except Exception as exc:
        rec.update(status='FAILED',error=type(exc).__name__+':'+str(exc)[:200])
      observations[channel]=rec
      # Commit only receipts and numeric/validation comparison; no raw HTML in GitHub.
      (directory/f'race_{n:02d}_{channel.lower()}_receipt.json').write_text(
        json.dumps({k:v for k,v in rec.items() if k!='roster'},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    expected=frozen(n)
    baseline=tuple((x['horse_number'],x['frame_number'],x['horse_name']) for x in expected['runners'])
    good_pc=observations['PC']['status']=='PARSED'
    good_sp=observations['SP']['status']=='PARSED'
    pc_match=good_pc and observations['PC']['roster']==baseline
    sp_match=good_sp and observations['SP']['roster']==baseline
    receipts.append({'race':n,'expected_count':len(baseline),
       'pc_snapshot_match':pc_match,'sp_snapshot_match':sp_match,
       'pc':{k:v for k,v in observations['PC'].items() if k!='roster'},
       'sp':{k:v for k,v in observations['SP'].items() if k!='roster'}})
  pc_latency=[x['pc']['network_ms'] for x in receipts if x['pc']['network_ms'] is not None and x['pc_snapshot_match']]
  sp_latency=[x['sp']['network_ms'] for x in receipts if x['sp']['network_ms'] is not None and x['sp_snapshot_match']]
  complete=len(pc_latency)==len(sp_latency)==len(RACES)
  result={'schema_version':'jra_pc_sp_empirical_benchmark.v1',
    'target_day':'2026-11-07','official_navigation_not_guessed':True,
    'sample_races':list(RACES),'races':receipts,
    'full_roster_parity':complete,
    'pc_median_network_ms':round(median(pc_latency),2) if complete else None,
    'sp_median_network_ms':round(median(sp_latency),2) if complete else None,
    'sp_network_gain_pct':round(100*(1-median(sp_latency)/median(pc_latency)),1) if complete else None,
    'pc_total_bytes':sum(x['pc'].get('raw_bytes',0) for x in receipts),
    'sp_total_bytes':sum(x['sp'].get('raw_bytes',0) for x in receipts),
    'pc_first_baseline':True,'allow_auto_switch':False,
    'odds_verified':False,'scratch_verified':False,
    'training_ready':False,'prediction_ready':False}
  (directory/'benchmark_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  return result
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='jra_pc_sp_benchmark');args=ap.parse_args()
 data=benchmark(args.out)
 print(json.dumps({k:v for k,v in data.items() if k!='races'},ensure_ascii=False))


def reconcile_saved_racecards(channels, frozen_snapshot, *, meeting_date, race, cutoff_utc, observed_utc):
  """Reuse the existing PC and SP parsers on locally saved original bytes only.

  A verified frozen reference is required. SP may replace a bad/unavailable PC
  record if its complete (number, frame, name) roster matches that reference.
  This proves no official current-day freshness, permission or sale status.
  """
  from datetime import datetime,timezone
  import hashlib
  def utc(v):
    if not isinstance(v,str):
      raise ValueError("timestamp_missing")
    dt=datetime.fromisoformat(v.replace('Z','+00:00'))
    if dt.tzinfo is None or dt.utcoffset().total_seconds()!=0:
      raise ValueError("timestamp_not_utc")
    return dt.astimezone(timezone.utc)
  if (not isinstance(channels,dict) or not set(channels).issubset({"PC","SP"})
          or not channels or not isinstance(frozen_snapshot,dict)
          or type(race) is not int or not 1<=race<=12):
    raise ValueError("offline_input_invalid")
  if (frozen_snapshot.get("race_number")!=race
          or frozen_snapshot.get("race_date")!=meeting_date
          or frozen_snapshot.get("roster_verified") is not True
          or not frozen_snapshot.get("runners")):
    raise ValueError("frozen_reference_mismatch")
  reference=tuple((row["horse_number"],row["frame_number"],row["horse_name"])
                  for row in frozen_snapshot["runners"])
  if len(reference)!=len(set(reference)) or not 2<=len(reference)<=18:
    raise ValueError("frozen_reference_roster_invalid")
  cutoff=utc(cutoff_utc); observed=utc(observed_utc)
  if observed>=cutoff:
    raise ValueError("cutoff_elapsed")
  outcomes={}
  for channel in ("PC","SP"):
    item=channels.get(channel)
    if item is None:
      outcomes[channel]={"status":"UNAVAILABLE"}
      continue
    if not isinstance(item,dict) or not isinstance(item.get("raw"),bytes):
      raise ValueError("source_bytes_invalid")
    raw=item["raw"]
    if not 0<len(raw)<=1_500_000:
      raise ValueError("source_bytes_invalid")
    captured=utc(item.get("captured_utc"))
    if captured>observed or captured>=cutoff:
      raise ValueError("source_not_before_cutoff")
    digest=hashlib.sha256(raw).hexdigest()
    if item.get("sha256")!=digest:
      raise ValueError("source_sha_mismatch")
    try:
      rows=(pc_rows(raw,race,meeting_date=meeting_date)
            if channel=="PC" else sp_rows(raw))
      valid=rows==reference
      outcomes[channel]={"status":"MATCH" if valid else "ROSTER_MISMATCH",
                         "source_sha256":digest,"captured_utc":captured.isoformat(),
                         "runner_count":len(rows)}
    except (ValueError,KeyError,TypeError) as exc:
      outcomes[channel]={"status":"PARSER_FAILED","source_sha256":digest,
                         "captured_utc":captured.isoformat(),
                         "error":str(exc)[:120]}
  valid=[x for x in ("PC","SP") if outcomes[x]["status"]=="MATCH"]
  chosen="PC" if "PC" in valid else "SP" if "SP" in valid else None
  return {"schema":"kyoto_p1_saved_pc_sp_roster_reconciliation.v1",
          "race_date":meeting_date,"race":race,"runner_count":len(reference),
          "sources":outcomes,"selected_channel":chosen,
          "fallback_to_sp":chosen=="SP",
          "reference_matched":chosen is not None,
          "state":"OFFLINE_ROSTER_RECONCILED" if chosen else "BLOCKED",
          "official_live_odds_verified":False,
          "predictions_authorized":False,"network_requests":0}


def assess_dual_channel_experiment(channels, frozen_snapshot, *,
                                   meeting_date, race, cutoff_utc, observed_utc):
  """Strict offline PC/SP original parity using the existing proven parsers.

  Unlike single-channel fallback, BOTH independently observed official URLs
  and BOTH byte-preserved racecards are required. This cannot certify odds.
  """
  from datetime import datetime
  from urllib.parse import urlsplit,parse_qs,urljoin
  from bs4 import BeautifulSoup
  import hashlib,re
  def utc(value):
    if type(value) is not str:
      raise ValueError("hybrid_timestamp_missing")
    try: stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc: raise ValueError("hybrid_timestamp_invalid") from exc
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds()!=0:
      raise ValueError("hybrid_timestamp_not_utc")
    return stamp
  if type(channels) is not dict or set(channels)-{"PC","SP"}:
    raise ValueError("hybrid_channels_invalid")
  # Reuse historical original-byte SHA, cutoff and runner comparison.
  result=reconcile_saved_racecards(channels,frozen_snapshot,
      meeting_date=meeting_date,race=race,cutoff_utc=cutoff_utc,
      observed_utc=observed_utc)
  status={}
  for channel,host in (("PC","jra.jp"),("SP","sp.jra.jp")):
    item=channels.get(channel)
    if item is None:
      status[channel]={"state":"MISSING_OFFICIAL_ORIGINAL"}
      continue
    url=item.get("source_url")
    # The flag alone is not evidence. Re-verify the exact official link
    # against an independently retained navigation original and its SHA.
    navigation=item.get("navigation_original")
    parent=item.get("navigation_parent_url")
    proof=(type(navigation) is bytes and 0<len(navigation)<=1_500_000
           and item.get("navigation_sha256")==hashlib.sha256(navigation).hexdigest()
           and type(parent) is str and
           urlsplit(parent).scheme=="https" and
           urlsplit(parent).hostname==host and
           urlsplit(parent).port is None and
           not urlsplit(parent).username and not urlsplit(parent).password)
    if proof:
      html=BeautifulSoup(navigation.decode("cp932",errors="replace"),"html.parser")
      observed_links={urljoin(parent,a.get("href","").strip())
                      for a in html.select("a[href]")
                      if a.get("href","").strip()}
      proof=url in observed_links
    try:
      u=urlsplit(url or "")
      q=parse_qs(u.query,strict_parsing=True)
      token=q["CNAME"][0]
      good=(u.scheme=="https" and u.hostname==host and
            u.port is None and not u.username and not u.password and
            not u.fragment and u.path=="/JRADB/accessD.html" and
            set(q)=={"CNAME"} and len(q["CNAME"])==1 and
            re.fullmatch(r"[ps]w[A-Za-z0-9]+/[A-Za-z0-9]+",token) and
            token.startswith("pw" if channel=="PC" else "sw") and
            meeting_date.replace("-","") in token and proof)
    except (TypeError,ValueError,KeyError,IndexError):
      good=False
    status[channel]={"state":"OFFICIAL_LINK_OBSERVED" if good
                     else "OFFICIAL_LINK_NOT_INDEPENDENTLY_PROVEN"}
  dual_links=all(status[c]["state"]=="OFFICIAL_LINK_OBSERVED"
                 for c in ("PC","SP"))
  both_match=all(result["sources"][c]["status"]=="MATCH"
                 for c in ("PC","SP"))
  times_ok=False
  if both_match and dual_links:
    a=utc(channels["PC"]["captured_utc"])
    b=utc(channels["SP"]["captured_utc"])
    times_ok=abs((a-b).total_seconds())<=900
  parity=bool(dual_links and both_match and times_ok)
  return {"schema":"kyoto_p1_pc_sp_independent_hybrid_experiment.v1",
          "race_date":meeting_date,"race_number":race,
          "channel_links":status,
          "channel_rosters":result["sources"],
          "independently_observed_both_urls":dual_links,
          "both_saved_racecards_match_verified_reference":both_match,
          "time_delta_within_15_minutes":times_ok,
          "dual_racecard_structure_parity":parity,
          "dual_market_originals_verified":False,
          "full_hybrid_experiment_pass":False,
          "state":("DUAL_RACECARDS_OFFLINE_MATCH_MARKETS_PENDING" if parity
                   else "DUAL_SOURCE_RACECARD_INCOMPLETE"),
          "prediction_ready":False,"training_ready":False,
          "network_requests":0}
