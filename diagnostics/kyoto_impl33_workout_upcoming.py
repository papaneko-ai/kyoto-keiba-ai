"""Freeze observed upcoming workout pages, not a confirmed official roster or prediction."""
import hashlib, json, os, time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from diagnostics.kyoto_impl33_whitegreen_probe import HOST, AGENT, JST, get, inspect
from diagnostics.kyoto_impl33_workout_all12 import INDEX, discover, seal

DAYS=('20261128','20261129')
# Two pages observed directly in previous research, supplement actual index links.
OBSERVED={'20261128':{9:HOST+'/race/20261128-kyoto-09/',11:HOST+'/race/20261128-kyoto-11/'},'20261129':{}}
def is_pre_day(day, captured_utc):
    t=datetime.fromisoformat(captured_utc.replace('Z','+00:00'))
    if t.utcoffset().total_seconds()!=0:raise ValueError('utc_required')
    return t.astimezone(JST).date()<date.fromisoformat(day[:4]+'-'+day[4:6]+'-'+day[6:])
def main():
    out=Path('upcoming_workout');out.mkdir(exist_ok=True)
    key=bytes.fromhex(os.environ['ARCHIVE_KEY'])
    if len(key)!=32:raise ValueError('archive_key')
    rp=RobotFileParser()
    try:robots=get(HOST+'/robots.txt').decode('utf8')
    except HTTPError as e:
        if e.code!=404:raise
        robots='User-agent: *\nDisallow:'
    rp.parse(robots.splitlines())
    delay=max(2,rp.crawl_delay(AGENT) or 0)
    if delay>15:raise ValueError('crawl_delay_budget')
    if not rp.can_fetch(AGENT,INDEX):raise ValueError('index_disallow')
    time.sleep(delay);idx=get(INDEX)
    report={'status':'UPCOMING_RESEARCH_IN_PROGRESS','jra_requests':0,'index_sha256':hashlib.sha256(idx).hexdigest(),
            'official_roster_verified':False,'production_coverage_authorized':False,'days':{}}
    for day in DAYS:
        urls=dict(OBSERVED[day]);urls.update(discover(idx,day))
        approved=tuple((day,n,u) for n,u in urls.items())
        result={'observed_links':len(urls),'races':[]};report['days'][day]=result
        for n in sorted(urls):
            item={'day':day,'race':n,'url':urls[n]}
            try:
                if not rp.can_fetch(AGENT,urls[n]):raise ValueError('robots_disallow')
                if not is_pre_day(day,datetime.now(timezone.utc).isoformat()):raise ValueError('not_before_race_day')
                time.sleep(delay);raw=get(urls[n]);stamp=datetime.now(timezone.utc).isoformat()
                if not is_pre_day(day,stamp):raise ValueError('not_before_race_day')
                aad=f'kyoto-workout-upcoming-v1|{os.environ["GITHUB_REPOSITORY"]}|{os.environ["GITHUB_RUN_ID"]}|{day}|{n}'.encode()
                name=f'{day}_r{n:02d}.aesgcm'
                item.update(source_sha256=hashlib.sha256(raw).hexdigest(),captured_utc=stamp,source_ciphertext_sha256=seal(out,name,raw,key,aad),archive_aad=aad.decode())
                receipt=inspect(raw,day,n,urls[n],stamp,approved)
                if receipt['result_section_present']:raise ValueError('result_section_present')
                item.update(receipt,status='PRE_DAY_SOURCE_FROZEN')
            except Exception as e:
                item.update(status='UNVERIFIED',error_type=type(e).__name__)
                if isinstance(e,ValueError):item['error_code']=str(e)[:100]
            result['races'].append(item)
            (out/'receipt.json').write_text(json.dumps(report,sort_keys=True,indent=2),encoding='utf8')
        result['frozen_races']=sum(x['status']=='PRE_DAY_SOURCE_FROZEN' for x in result['races'])
    report['status']='UPCOMING_RESEARCH_FINISHED'
    (out/'receipt.json').write_text(json.dumps(report,sort_keys=True,indent=2),encoding='utf8')
    print('UPCOMING_WORKOUT='+json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
