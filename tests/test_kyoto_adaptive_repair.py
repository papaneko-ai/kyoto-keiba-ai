import unittest
from diagnostics.kyoto_adaptive_repair import recover_action,RepairRejected,lexical_call,regex_call
DAY="20261129"
def page(form,control):return ("<html><body>"+form+control+"</body></html>").encode("utf8")
def form(fid="unseen",action=""):return f'<form id="{fid}" method="post" action="{action}"><input type="hidden" name="cname"></form>'
class AdaptiveRepairTests(unittest.TestCase):
 def test_unseen_structural_combinations(self):
  for channel,prefix in (("PC","pw"),("SP","sw")):
   for k in range(8):
    token=prefix+"01dli00/"+f"{k:02X}"
    call=f"doAction {' '*(k+1)}('/JRADB/accessD.html', '{token}'); return false;"
    control=f'<button onclick="{call}">出馬表</button>' if k%2 else f'<a href="javascript:{call}">出馬表</a>'
    raw=page(form("new"+str(k),"/JRADB/accessD.html" if k%3 else ""),control)
    a=recover_action(raw,DAY,channel,"entry")
    self.assertEqual(a[:3],("/JRADB/accessD.html",token,"出馬表"))
    self.assertEqual(a,recover_action(raw,DAY,channel,"entry"))
    self.assertFalse(a[3]["race_data_certified"])
 def test_meeting_identity(self):
  token="sw01drl00082026050820261129/F8"
  raw=page(form(),f'<a onclick="doAction (\'/JRADB/accessD.html\',\'{token}\')">京都 開催</a>')
  self.assertEqual(recover_action(raw,DAY,"SP","meeting")[1],token)
  for day,c in (("20261128","SP"),(DAY,"PC")):
   with self.assertRaises(RepairRejected):recover_action(raw,day,c,"meeting")
 def test_adversarial(self):
  call="doAction ('/JRADB/accessD.html','pw01dli00/F3')"
  a=f'<a onclick="{call}">出馬表</a>'
  for raw in (page(form(action="https://evil.invalid"),a),page(form()+form("other"),a),page(form(),a+a.replace("F3","F4")),page(form(),a.replace("出馬表","別開催")),page(form(),a.replace("doAction","otherAction")),page(form(),a.replace(call,call+";other()")),page(form(),a.replace("/JRADB/accessD.html","//evil.invalid/JRADB/accessD.html")),page(form(),a.replace("<a ","<a formaction='https://evil.invalid' ")),page(form().replace("</form>",'<input name="extra"></form>'),a),page(form(),'<base href="https://evil.invalid/">'+a),page(form(),a.replace("<a ","<a hidden "))):
   with self.assertRaises(RepairRejected):recover_action(raw,DAY,"PC","entry")
 def test_literal_grammar_no_execution(self):
  for x in ("doAction('/JRADB/accessD.html','pw01dli00/F3');alert(1)","doAction('/JRADB/accessD.html',x)","doAction('/JRADB/accessD.html','pw01dli00/F3'+x)"):
   self.assertIsNone(lexical_call(x));self.assertIsNone(regex_call(x))
if __name__=="__main__":unittest.main()
