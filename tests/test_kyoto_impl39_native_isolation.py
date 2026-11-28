"""Exact trigger-only delta against approved PR168, without source requests."""
import copy, subprocess, unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
import yaml
from diagnostics.kyoto_impl30_collector_selection import DEPLOYED_RECEIPT
SUNDAY_PIN=DEPLOYED_RECEIPT["override"]
SATURDAY_READER="c289c5ec4e6ad322a7e08acf173da3352ed23dba"
DAY_REF="${{ inputs.race_day == '20261129' && '"+SUNDAY_PIN+"' || '"+SATURDAY_READER+"' }}"
ROOT=Path(__file__).resolve().parents[1]
PREFIX="kyoto-20261128-29-"
BASE="425ba294b939a819038afa446a6158d83e2eef40"
SLOTS={"two-source-production-observer":["15 0 28 11 *","15 1 28 11 *","5 2 28 11 *","50 2 28 11 *","15 0 29 11 *","15 1 29 11 *","10 2 29 11 *","55 2 29 11 *"],"auxiliary-refresh":["30 3 28 11 *","30 4 28 11 *","30 5 28 11 *","30 6 28 11 *","30 3 29 11 *","30 4 29 11 *","30 5 29 11 *","30 6 29 11 *"],"postrace-evidence":["0 10 28 11 *","0 13 28 11 *","0 10 29 11 *","0 13 29 11 *"],"result-handoff":["0 12 28 11 *","0 12 29 11 *"],"workout-source":["30 11 27 11 *","30 22 27 11 *","30 11 28 11 *","30 22 28 11 *"]}
NAMES=tuple(SLOTS)+("cushion-source",)
CONFIRM={"two-source-production-observer":"NOV28-29-OBSERVE-READ-ONLY","auxiliary-refresh":"NOV28-29-AUXILIARY-SOURCE-ONLY","postrace-evidence":"NOV28-29-POSTRACE-SOURCE-ONLY","result-handoff":"NOV28-29-HANDOFF-ONLY","workout-source":"NOV28-29-WORKOUT-SOURCE-ONLY","cushion-source":"NOV28-29-CUSHION-SOURCE-ONLY"}
SOURCE_GROUP="${{ github.event_name == 'workflow_dispatch' && format('kyoto-20261128-29-source-{0}', inputs.race_day == '20261128' && '20261128' || '20261129') || format('kyoto-native-isolated-{0}', github.run_id) }}"
WORKOUT_GROUP="${{ (github.event_name == 'workflow_dispatch' || (github.event_name == 'workflow_run' && github.event.workflow_run.event == 'workflow_dispatch')) && format('kyoto-nov28-29-workout-{0}', (github.event_name == 'workflow_dispatch' && inputs.race_day == '20261128' || github.event_name == 'workflow_run' && startsWith(github.event.workflow_run.created_at, '2026-11-28')) && '20261128' || '20261129') || format('kyoto-native-isolated-{0}', github.run_id) }}"
CUSHION_IF="${{ github.repository == 'papaneko-ai/kyoto-keiba-ai' && github.ref == 'refs/heads/main' && ((github.event_name == 'workflow_dispatch' && inputs.confirmation == 'NOV28-29-CUSHION-SOURCE-ONLY') || (github.event_name == 'workflow_run' && github.event.workflow_run.head_repository.full_name == github.repository && github.event.workflow_run.head_branch == 'main' && (startsWith(github.event.workflow_run.created_at, '2026-11-28') || startsWith(github.event.workflow_run.created_at, '2026-11-29')) && github.event.workflow_run.event == 'workflow_dispatch' && (contains(github.event.workflow_run.created_at, 'T00:') || contains(github.event.workflow_run.created_at, 'T01:') || contains(github.event.workflow_run.created_at, 'T03:')))) }}"
HANDOFF_IF="${{ github.event_name == 'workflow_dispatch' && inputs.confirmation == 'NOV28-29-HANDOFF-ONLY' }}"
def doc(name,base=False):
    p=".github/workflows/"+PREFIX+name+".yml"
    raw=subprocess.check_output(["git","show",BASE+":"+p],cwd=ROOT,text=True) if base else (ROOT/p).read_text()
    return yaml.load(raw,Loader=yaml.BaseLoader)
def diagnostic_crons():
    return [s["cron"] for s in doc("native-scheduler-diagnostic")["on"]["schedule"]]
class Isolation(unittest.TestCase):
    def test_exact_live_workflow_delta(self):
        for n in NAMES:
            with self.subTest(workflow=n):
                original=doc(n,True); expected=copy.deepcopy(original)
                if n in SLOTS:
                    self.assertEqual([s["cron"] for s in expected["on"].pop("schedule")],SLOTS[n])
                if n in ("two-source-production-observer","auxiliary-refresh","postrace-evidence"):
                    expected["concurrency"]["group"]=SOURCE_GROUP
                    for j in expected["jobs"].values():
                        old="github.event_name == 'schedule' || (github.event_name == 'workflow_dispatch' && inputs.confirmation == '"+CONFIRM[n]+"')"
                        self.assertEqual(j["if"].count(old),1)
                        j["if"]=j["if"].replace(old,"(github.event_name == 'workflow_dispatch' && inputs.confirmation == '"+CONFIRM[n]+"')")
                elif n=="result-handoff":
                    expected["jobs"]["authenticated-handoff"]["if"]=HANDOFF_IF
                elif n=="workout-source":
                    expected["concurrency"]["group"]=WORKOUT_GROUP
                    j=expected["jobs"]["source-only"]
                    j["if"]=j["if"].replace("(github.event_name == 'schedule' || (github.event_name == 'workflow_dispatch'","((github.event_name == 'workflow_dispatch'").replace("(github.event.workflow_run.event == 'schedule' || github.event.workflow_run.event == 'workflow_dispatch')","(github.event.workflow_run.event == 'workflow_dispatch')")
                elif n=="cushion-source":
                    expected["jobs"]["cushion-source-only"]["if"]=CUSHION_IF
                # Only the separately verified Sunday source selection may change.
                if n=="two-source-production-observer":
                    expected["jobs"]["select-collector"]["env"]["SUNDAY_OVERRIDE_SHA"]=SUNDAY_PIN
                elif n=="auxiliary-refresh":
                    j=expected["jobs"]["afternoon-auxiliary-source"]
                    j["steps"][0]["with"]["ref"]=DAY_REF
                    for s in j["steps"]:
                        if 'test "$(git rev-parse HEAD)"' in s.get("run",""):
                            s["run"]=s["run"].replace('test "$(git rev-parse HEAD)" = '+repr(SATURDAY_READER),'test "$(git rev-parse HEAD)" = "'+DAY_REF+'"')
                elif n=="result-handoff":
                    expected["jobs"]["authenticated-handoff"]["steps"][0]["with"]["ref"]=DAY_REF
                self.assertEqual(doc(n),expected)
                self.assertNotIn("schedule",doc(n)["on"])
                self.assertEqual(doc(n)["on"]["workflow_dispatch"],original["on"]["workflow_dispatch"])
    def test_independent_closure_reader_only_sunday_changes(self):
        path=".github/workflows/kyoto-weekend-closure-review.yml"
        previous=subprocess.check_output(["git","show","457fcf075143b7f80a769b259fa1b9f5d2987abf:"+path],cwd=ROOT,text=True)
        expected=previous.replace("ref: '"+SATURDAY_READER+"'","ref: ${{ env.TARGET_DAY == '20261129' && '"+SUNDAY_PIN+"' || '"+SATURDAY_READER+"' }}")
        self.assertEqual((ROOT/path).read_text(),expected)
    def test_native_probe(self):
        d=doc("native-scheduler-diagnostic")
        self.assertEqual(set(d["on"]),{"schedule"})
        expected=[c for seq in SLOTS.values() for c in seq]
        self.assertEqual(diagnostic_crons(),expected)
        self.assertEqual(len(set(expected)),26)
        self.assertNotIn("concurrency",d)
        self.assertEqual(d["permissions"],{})
        self.assertEqual(set(d["jobs"]),{"record-only"})
        j=d["jobs"]["record-only"]
        self.assertEqual(j["timeout-minutes"],"1")
        self.assertEqual(set(j["env"]),{"NOMINAL_CRON"})
        self.assertEqual(len(j["steps"]),1)
        s=j["steps"][0]
        self.assertNotIn("uses",s)
        for forbidden in ("secrets.","GH_TOKEN","curl ","gh ","urllib","requests.","fetch(","checkout","dispatch --"):
            self.assertNotIn(forbidden,s["run"])
        self.assertIn("source_http_requests=0",s["run"])
        self.assertIn("source_success_certified=False",s["run"])
        self.assertNotIn(d["name"]," ".join(str(doc(n)["on"]) for n in NAMES))
    def test_external_slot_map_and_manual_inputs(self):
        # Existing v3 timer plan (#124); plan check, not provider proof.
        actual={}
        for n,crons in SLOTS.items():
            for c in crons:
                m,h,d,mo,_=c.split()
                t=datetime(2026,int(mo),int(d),int(h),int(m),tzinfo=timezone.utc)+timedelta(hours=9,minutes=2)
                actual[t.strftime("%m-%d %H:%M")]=n
        self.assertEqual(len(actual),26)
        expected={}
        for day,morning in ((28,("09:17","10:17","11:07","11:52")),(29,("09:17","10:17","11:12","11:57"))):
            for t in morning:expected[f"11-{day} "+t]="two-source-production-observer"
            for t in ("12:32","13:32","14:32","15:32"):expected[f"11-{day} "+t]="auxiliary-refresh"
            for t in ("19:02","22:02"):expected[f"11-{day} "+t]="postrace-evidence"
            expected[f"11-{day} 21:02"]="result-handoff"
            expected[f"11-{day} 07:32"]="workout-source"
            expected[f"11-{day-1} 20:32"]="workout-source"
        self.assertEqual(actual,expected)
        for n in NAMES:
            inputs=doc(n)["on"]["workflow_dispatch"]["inputs"]
            self.assertEqual(inputs["race_day"]["options"],["20261128","20261129"])
            self.assertEqual(inputs["confirmation"]["required"],"true")
            self.assertIn(CONFIRM[n],inputs["confirmation"]["description"])
    def test_legacy_event_and_lock_isolation(self):
        for n in ("two-source-production-observer","auxiliary-refresh","postrace-evidence"):
            d=doc(n)
            self.assertEqual(d["concurrency"]["group"],SOURCE_GROUP)
            self.assertEqual(d["concurrency"]["queue"],"max")
            self.assertEqual(d["concurrency"]["cancel-in-progress"],"false")
            for j in d["jobs"].values():
                self.assertNotIn("github.event_name == 'schedule'",j["if"])
                self.assertIn("github.event_name == 'workflow_dispatch'",j["if"])
        d=doc("workout-source")
        self.assertEqual(d["concurrency"]["group"],WORKOUT_GROUP)
        for n,j in (("workout-source","source-only"),("cushion-source","cushion-source-only")):
            cond=doc(n)["jobs"][j]["if"]
            self.assertNotIn("github.event_name == 'schedule'",cond)
            self.assertNotIn("github.event.workflow_run.event == 'schedule'",cond)
            self.assertIn("github.event.workflow_run.event == 'workflow_dispatch'",cond)
            self.assertIn("inputs.confirmation",cond)
            self.assertNotIn("conclusion == 'success'",cond)
        self.assertNotIn("github.event_name == 'schedule'",doc("result-handoff")["jobs"]["authenticated-handoff"]["if"])
if __name__=="__main__":unittest.main()
