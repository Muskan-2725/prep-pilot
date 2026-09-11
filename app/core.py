"""PrepPilot V1 domain services: persistent learner state and honest knowledge fallback."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, sqlite3, time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("PREPPILOT_DB", "data/preppilot.db"))
SECRET = os.getenv("PREPPILOT_SECRET", "development-only-change-me")
TOPICS = {
 "deadlocks": ("Operating Systems", "Deadlocks"), "scheduling": ("Operating Systems", "CPU Scheduling"),
 "transactions": ("DBMS", "Transactions"), "normalization": ("DBMS", "Normalization"),
 "graphs": ("Algorithms", "Graph Algorithms"), "tcp": ("Computer Networks", "TCP"),
}
QUESTIONS = [
 ("deadlock-1","deadlocks",.35,"mcq","Which is not a Coffman deadlock condition?",["Mutual exclusion","Hold and wait","Preemption","Circular wait"],2,"Deadlock requires no preemption, not preemption."),
 ("deadlock-2","deadlocks",.55,"mcq","A safe state in Banker’s algorithm means:",["Deadlock exists","A completion sequence exists","All resources are free","Preemption is required"],1,"A safe sequence lets every process eventually complete."),
 ("deadlock-3","deadlocks",.7,"mcq","Breaking which condition can prevent deadlock by a resource ordering rule?",["Mutual exclusion","Hold and wait","No preemption","Circular wait"],3,"A global order prevents circular wait."),
 ("sched-1","scheduling",.4,"mcq","Which scheduling algorithm can cause starvation without aging?",["FCFS","Round Robin","Priority scheduling","FIFO paging"],2,"Low-priority processes can starve under priority scheduling without aging."),
 ("tx-1","transactions",.4,"mcq","Which ACID property preserves committed data after a crash?",["Atomicity","Consistency","Isolation","Durability"],3,"Durability makes committed work survive failures."),
 ("norm-1","normalization",.5,"mcq","BCNF requires that every determinant is:",["A foreign key","A candidate key","Non-prime","Multi-valued"],1,"In BCNF each determinant must be a superkey."),
 ("graph-1","graphs",.4,"mcq","BFS on an unweighted graph finds:",["A minimum spanning tree always","Shortest hop-count paths","Only cycles","Topological order"],1,"BFS explores in increasing edge distance."),
 ("tcp-1","tcp",.4,"mcq","TCP provides:",["Unreliable datagrams","Reliable ordered byte stream","Only routing","Only encryption"],1,"TCP supplies reliable ordered delivery."),
]
SOURCES = [{"title":"Official GATE website", "url":"https://gate2026.iitg.ac.in/", "quality":"official", "checked_at":"2026-09-11"}]

def conn():
 DB_PATH.parent.mkdir(parents=True, exist_ok=True); c=sqlite3.connect(DB_PATH, timeout=5); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c

def init_db():
 c=conn()
 try:
  c.executescript("""
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS profiles(user_id INTEGER PRIMARY KEY REFERENCES users(id),exam TEXT NOT NULL,target TEXT NOT NULL,exam_date TEXT,hours_per_week INTEGER NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS topic_states(user_id INTEGER REFERENCES users(id),topic TEXT,subject TEXT,mastery REAL NOT NULL,confidence REAL NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,correct INTEGER NOT NULL DEFAULT 0,last_mistake TEXT,trend REAL NOT NULL DEFAULT 0,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,topic));
  CREATE TABLE IF NOT EXISTS questions(id TEXT PRIMARY KEY,topic TEXT,subject TEXT,difficulty REAL,kind TEXT,prompt TEXT,choices TEXT,answer INTEGER,explanation TEXT,source TEXT);
  CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),question_id TEXT REFERENCES questions(id),topic TEXT,correct INTEGER,mistake_type TEXT,confidence INTEGER,elapsed_seconds INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),version INTEGER NOT NULL,rationale TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,version));
  CREATE TABLE IF NOT EXISTS plan_items(id INTEGER PRIMARY KEY,plan_id INTEGER REFERENCES plans(id),topic TEXT,hours REAL,reason TEXT,completed INTEGER NOT NULL DEFAULT 0);
  CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),role TEXT,content TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE INDEX IF NOT EXISTS idx_attempts_user_topic_time ON attempts(user_id,topic,created_at DESC);
  CREATE INDEX IF NOT EXISTS idx_messages_user_time ON messages(user_id,created_at DESC);
  """)
  for q in QUESTIONS: c.execute("INSERT OR IGNORE INTO questions VALUES(?,?,?,?,?,?,?,?,?,?)",(q[0],q[1],TOPICS[q[1]][0],q[2],q[3],q[4],json.dumps(q[5]),q[6],q[7],"PrepPilot authored practice"))
  c.commit()
 finally: c.close()

def hash_password(password):
 salt=os.urandom(16); return base64.b64encode(salt+hashlib.pbkdf2_hmac("sha256",password.encode(),salt,310000)).decode()
def verify_password(password,stored):
 raw=base64.b64decode(stored); return hmac.compare_digest(raw[16:],hashlib.pbkdf2_hmac("sha256",password.encode(),raw[:16],310000))
def token(uid):
 p=base64.urlsafe_b64encode(json.dumps({"sub":uid,"exp":int(time.time()+86400)}).encode()).decode().rstrip("="); return p+"."+hmac.new(SECRET.encode(),p.encode(),hashlib.sha256).hexdigest()
def user_from_token(value):
 try:
  p,s=value.split(".");
  if not hmac.compare_digest(s,hmac.new(SECRET.encode(),p.encode(),hashlib.sha256).hexdigest()): return None
  d=json.loads(base64.urlsafe_b64decode(p+"===")); return int(d["sub"]) if d["exp"]>=time.time() else None
 except Exception: return None

def create_user(email,password):
 with conn() as c:
  uid=c.execute("INSERT INTO users(email,password_hash) VALUES(?,?)",(email,hash_password(password))).lastrowid
  for topic,(subject,_) in TOPICS.items(): c.execute("INSERT INTO topic_states(user_id,topic,subject,mastery,confidence) VALUES(?,?,?,?,?)",(uid,topic,subject,.5,.5))
 return uid

def onboarding(uid,d):
 exam=str(d.get("exam","GATE CSE")); target=str(d.get("target","Qualify confidently")); hours=int(d["hours_per_week"]); exam_date=str(d.get("exam_date") or "")
 if exam!="GATE CSE" or not 2<=hours<=80: raise ValueError("Choose GATE CSE and 2–80 weekly hours.")
 try:
  if exam_date: date.fromisoformat(exam_date)
 except ValueError: raise ValueError("exam_date must be YYYY-MM-DD")
 confidences=d.get("confidence",{})
 with conn() as c:
  c.execute("INSERT INTO profiles(user_id,exam,target,exam_date,hours_per_week) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET exam=excluded.exam,target=excluded.target,exam_date=excluded.exam_date,hours_per_week=excluded.hours_per_week,updated_at=CURRENT_TIMESTAMP",(uid,exam,target,exam_date,hours))
  for topic in TOPICS:
   if topic in confidences:
    v=float(confidences[topic]);
    if not 0<=v<=1: raise ValueError("Confidence values must be between 0 and 1.")
    c.execute("UPDATE topic_states SET confidence=?,mastery=? WHERE user_id=? AND topic=?",(v,round(.35+.5*v,2),uid,topic))
 return dashboard(uid)
def states(uid):
 with conn() as c: return [dict(x) for x in c.execute("SELECT * FROM topic_states WHERE user_id=? ORDER BY mastery",(uid,))]
def _attempt_summary(uid,topic):
 with conn() as c: rows=c.execute("SELECT correct,mistake_type FROM attempts WHERE user_id=? AND topic=? ORDER BY id DESC LIMIT 5",(uid,topic)).fetchall()
 return rows
def priority(uid,state):
 recent=_attempt_summary(uid,state["topic"]); accuracy=sum(x["correct"] for x in recent)/len(recent) if recent else None
 score=(1-state["mastery"])*.7+(1-state["confidence"])*.15+(1-(accuracy if accuracy is not None else state["mastery"]))* .15
 return score,accuracy,len(recent)
def recommendation(uid):
 ss=states(uid); ranked=sorted(((priority(uid,s),s) for s in ss),key=lambda x:x[0][0],reverse=True); (score,acc,n),s=ranked[0]
 reason=(f"{s['subject']} · {TOPICS[s['topic']][1]} is lowest at {round(s['mastery']*100)}% mastery." if not n else f"{TOPICS[s['topic']][1]} accuracy is {round((acc or 0)*100)}% across the latest {n} attempts; it needs targeted retrieval practice.")
 return s,reason
def dashboard(uid):
 with conn() as c:
  p=c.execute("SELECT * FROM profiles WHERE user_id=?",(uid,)).fetchone(); total=c.execute("SELECT COUNT(*) FROM attempts WHERE user_id=?",(uid,)).fetchone()[0]; recent=[dict(x) for x in c.execute("SELECT topic,correct,mistake_type,created_at FROM attempts WHERE user_id=? ORDER BY id DESC LIMIT 5",(uid,))]
 ss=states(uid); focus,reason=recommendation(uid); countdown=None
 if p and p["exam_date"]:
  countdown=(date.fromisoformat(p["exam_date"])-date.today()).days
 return {"profile":dict(p) if p else None,"attempt_count":total,"topics":ss,"weaknesses":ss[:3],"improving":[s for s in ss if s["trend"]>.05],"recent_attempts":recent,"today":{"topic":focus["topic"],"label":TOPICS[focus["topic"]][1],"reason":reason,"action":"Complete 3 targeted questions, then review the explanation."},"exam_countdown_days":countdown,"zero_history":total==0}
def build_plan(uid):
 d=dashboard(uid); p=d["profile"]
 if not p: raise ValueError("Complete onboarding before generating a plan.")
 ranked=sorted(states(uid),key=lambda s:priority(uid,s)[0],reverse=True); hours=p["hours_per_week"]
 with conn() as c:
  version=c.execute("SELECT COALESCE(MAX(version),0)+1 FROM plans WHERE user_id=?",(uid,)).fetchone()[0]
  rationale=d["today"]["reason"]
  pid=c.execute("INSERT INTO plans(user_id,version,rationale) VALUES(?,?,?)",(uid,version,rationale)).lastrowid
  items=[]
  for i,s in enumerate(ranked[:4]):
   allocation=round(hours*([.4,.25,.2,.15][i]),1); _,acc,n=priority(uid,s); why=(f"Recent accuracy {round(acc*100)}% across {n} attempts." if n else f"Onboarding confidence is {round(s['confidence']*100)}%.")
   item={"topic":s["topic"],"label":TOPICS[s["topic"]][1],"hours":allocation,"reason":why}; items.append(item); c.execute("INSERT INTO plan_items(plan_id,topic,hours,reason) VALUES(?,?,?,?)",(pid,s["topic"],allocation,why))
 return {"version":version,"rationale":rationale,"items":items}
def practice(uid,topic=None,difficulty=None,count=1):
 focus,_=recommendation(uid); selected=topic or focus["topic"]; count=max(1,min(5,int(count))); target=float(difficulty) if difficulty is not None else float(next(s for s in states(uid) if s["topic"]==selected)["mastery"]+.1)
 with conn() as c: rows=[dict(x) for x in c.execute("SELECT * FROM questions WHERE topic=? ORDER BY ABS(difficulty-?) LIMIT ?",(selected,target,count))]
 return [{k:v for k,v in r.items() if k not in ("answer",)} | {"choices":json.loads(r["choices"])} for r in rows]
def evaluate(uid,d):
 qid=str(d["question_id"]); selected=int(d["selected"]); confidence=int(d.get("confidence",3)); elapsed=int(d.get("elapsed_seconds",0)); self_mistake=d.get("mistake_type")
 if confidence not in range(1,6): raise ValueError("Confidence must be 1–5.")
 with conn() as c:
  q=c.execute("SELECT * FROM questions WHERE id=?",(qid,)).fetchone()
  if not q: raise ValueError("Unknown question")
  choices=json.loads(q["choices"])
  if selected not in range(len(choices)): raise ValueError("Selected answer is outside the available choices.")
  correct=selected==q["answer"]; mistake="correct" if correct else (self_mistake if self_mistake in {"conceptual","careless","misread"} else ("careless" if confidence>=4 else "conceptual"))
  s=c.execute("SELECT * FROM topic_states WHERE user_id=? AND topic=?",(uid,q["topic"])).fetchone(); attempts=s["attempts"]+1; corrects=s["correct"]+int(correct); observed=corrects/attempts; delta=(.18 if correct else -.16)*(1+(.1 if q["difficulty"]>.6 else 0)); mastery=round(max(.05,min(.95,.7*s["mastery"]+.3*observed+delta)),2); trend=round(mastery-s["mastery"],2)
  c.execute("UPDATE topic_states SET mastery=?,attempts=?,correct=?,last_mistake=?,trend=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND topic=?",(mastery,attempts,corrects,None if correct else mistake,trend,uid,q["topic"]))
  c.execute("INSERT INTO attempts(user_id,question_id,topic,correct,mistake_type,confidence,elapsed_seconds) VALUES(?,?,?,?,?,?,?)",(uid,qid,q["topic"],int(correct),mistake,confidence,elapsed));
 return {"correct":correct,"mistake_type":mistake,"explanation":q["explanation"],"mastery":mastery,"recommendation":("Recovery signal: mastery improved; try a slightly harder question." if trend>.05 else f"Review {TOPICS[q['topic']][1]} and retry targeted practice."),"dashboard":dashboard(uid)}
def mentor(uid,message):
 d=dashboard(uid); focus=d["today"]; weak=focus["label"]; low=next(s for s in d["topics"] if s["topic"]==focus["topic"])
 text=(f"Your current focus is {weak}: {focus['reason']} ")
 if "deadlock" in message.lower(): text+="For deadlocks, reason from the four necessary conditions: mutual exclusion, hold-and-wait, no preemption, and circular wait. Try naming one prevention strategy and I will check it."
 else: text+=f"Ask a GATE CSE concept question, or complete practice first. I will use your {low['attempts']} recorded attempts and {round(low['mastery']*100)}% mastery when recommending the next step."
 with conn() as c: c.execute("INSERT INTO messages(user_id,role,content) VALUES(?,?,?)",(uid,"user",message)); c.execute("INSERT INTO messages(user_id,role,content) VALUES(?,?,?)",(uid,"assistant",text))
 return {"answer":text,"context":{"focus":weak,"mastery":low["mastery"],"attempts":low["attempts"]},"mode":"deterministic learner-aware fallback"}
def research(query):
 return {"answer":"Live web research is not configured in this zero-cost local V1. Use the official GATE website for current policy; PrepPilot does not infer date-sensitive rules without retrieved evidence.","query":query,"sources":SOURCES,"confidence":"unavailable","mode":"honest fallback"}
