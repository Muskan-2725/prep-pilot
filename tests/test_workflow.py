import json
from io import BytesIO
from pathlib import Path
from app import core
from app.server import app

def call(path,method="GET",data=None,token=None,query=""):
 raw=json.dumps(data or {}).encode(); result={}
 def start(status,headers): result["status"]=status
 env={"REQUEST_METHOD":method,"PATH_INFO":path,"QUERY_STRING":query,"wsgi.input":BytesIO(raw),"CONTENT_LENGTH":str(len(raw))}
 if token: env["HTTP_AUTHORIZATION"]="Bearer "+token
 payload=json.loads(b"".join(app(env,start)))
 return result["status"], payload
def setup(tmp_path,monkeypatch): monkeypatch.setattr(core,"DB_PATH",Path(tmp_path)/"db.sqlite")
def onboard(token): return call("/api/onboarding","PUT",{"exam":"GATE CSE","target":"Top 500","exam_date":"2027-02-01","hours_per_week":10,"confidence":{"deadlocks":.1,"graphs":.8}},token)
def test_real_adaptive_loop(tmp_path,monkeypatch):
 setup(tmp_path,monkeypatch); _,a=call("/api/auth/signup","POST",{"email":"a@example.com","password":"secure-pass-123"}); t=a["token"]
 assert onboard(t)[0].startswith("200"); _,before=call("/api/dashboard",token=t); assert before["today"]["topic"]=="deadlocks"
 _,qs=call("/api/practice",token=t,query="topic=deadlocks&count=1"); q=qs["questions"][0]
 _,bad=call("/api/attempts","POST",{"question_id":q["id"],"selected":0,"confidence":2,"mistake_type":"conceptual"},t); assert bad["correct"] is False and bad["mistake_type"]=="conceptual"
 _,after=call("/api/dashboard",token=t); dead=next(x for x in after["topics"] if x["topic"]=="deadlocks"); assert dead["attempts"]==1 and dead["mastery"]<.4
 _,plan=call("/api/plans/generate","POST",{},t); assert plan["items"][0]["topic"]=="deadlocks" and "accuracy" in plan["rationale"]
 _,mentor=call("/api/mentor","POST",{"message":"help with deadlocks"},t); assert mentor["context"]["attempts"]==1
 _,good=call("/api/attempts","POST",{"question_id":"deadlock-2","selected":1,"confidence":4},t); assert good["correct"] is True and "Recovery" in good["recommendation"]
def test_auth_validation_and_isolation(tmp_path,monkeypatch):
 setup(tmp_path,monkeypatch); _,a=call("/api/auth/signup","POST",{"email":"a@example.com","password":"secure-pass-123"}); _,b=call("/api/auth/signup","POST",{"email":"b@example.com","password":"secure-pass-123"})
 assert call("/api/dashboard")[0].startswith("401"); onboard(a["token"]); _,p=call("/api/profile",token=b["token"]); assert p["profile"] is None and p["attempt_count"]==0
 assert call("/api/onboarding","PUT",{"hours_per_week":1},a["token"])[0].startswith("422")
 assert call("/api/attempts","POST",{"question_id":"nope","selected":0},a["token"])[0].startswith("422")
def test_zero_history_and_honest_research(tmp_path,monkeypatch):
 setup(tmp_path,monkeypatch); _,a=call("/api/auth/signup","POST",{"email":"z@example.com","password":"secure-pass-123"}); onboard(a["token"])
 _,d=call("/api/dashboard",token=a["token"]); assert d["zero_history"] is True and d["exam_countdown_days"] is not None
 _,r=call("/api/research",token=a["token"],query="q=latest+syllabus"); assert r["confidence"]=="unavailable" and r["query"]=="latest syllabus"
