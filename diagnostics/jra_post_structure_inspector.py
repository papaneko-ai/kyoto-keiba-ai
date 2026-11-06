"""Structure-only audit for single captured official JRA HTML; do not publish raw HTML."""
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup
import json,re,argparse

def inspect(raw):
 s=BeautifulSoup(raw.decode('cp932',errors='replace'),'html.parser')
 text=s.get_text(' ',strip=True)
 clicks=[]
 for a in s.select('a[onclick]'):
  action=a.get('onclick','')
  if "doAction" in action and any(t in action for t in ('accessD.html','accessU.html','accessR.html')):
   clicks.append({'label':a.get_text(' ',strip=True)[:42],
                  'endpoint':next((t for t in ('accessD.html','accessU.html','accessR.html') if t in action),''),
                  'action_signature':bool(re.search(r"doAction\s*\(",action))})
 classes=Counter()
 for el in s.select('[class]'):
  for c in el.get('class',[]):classes[c]+=1
 return {'title':s.title.get_text(' ',strip=True) if s.title else None,
  'has_horse_name_marumo':"マルモリマイベスト" in text,
  'has_kyoto':"京都" in text,'has_race_no_1':"1R" in text,
  'has_horse_number':"馬番" in text,'has_racecard':"出馬表" in text,
  'counts':{tag:len(s.select(tag)) for tag in ('table','tr','td','div','form','script','iframe','a','select','input')},
  'visible_start':text[:420],
  'likely_class_names':classes.most_common(24),
  'jra_navigation_links':clicks[:12],
  'all_runner_links_count':sum(1 for x in clicks if x['endpoint'] in ('accessU.html','accessR.html')),
  'racecard_structure_verified':False,
  'training_ready':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);args=p.parse_args()
 raw=Path(args.source).read_bytes();out=inspect(raw)
 dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
