"""Deterministic MVP services: persistence, auth, grounded content and adaptation."""
from __future__ import annotations

import base64, hashlib, hmac, json, os, sqlite3, time
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.getenv("PREPPILOT_DATA_DIR", "data"))
DB_PATH = Path(os.getenv("PREPPILOT_DB", str(DATA_DIR / "preppilot.db")))
SECRET = os.getenv("PREPPILOT_SECRET", "development-only-change-me")

TOPICS = {
    "operating_systems": {"name": "Operating Systems", "keywords": ["deadlock", "scheduling", "process", "memory"], "baseline": 0.45},
    "dbms": {"name": "DBMS", "keywords": ["transaction", "normalization", "sql", "database"], "baseline": 0.45},
    "algorithms": {"name": "Algorithms", "keywords": ["graph", "complexity", "algorithm", "dp"], "baseline": 0.50},
    "computer_networks": {"name": "Computer Networks", "keywords": ["tcp", "network", "routing", "ip"], "baseline": 0.45},
}
SOURCES = [{"id": "gate-official", "title": "GATE official website", "url": "https://gate2026.iitg.ac.in/", "quality": "official", "checked_at": "2026-09-11"}]
QUESTIONS = [
 {"id":"os-deadlock-1", "topic":"operating_systems", "difficulty":0.45, "prompt":"Which condition is NOT one of Coffman's necessary conditions for deadlock?", "choices":["Mutual exclusion", "Hold and wait", "Preemption", "Circular wait"], "answer":2, "explanation":"No preemption is required for deadlock; preemption is not a deadlock condition."},
 {"id":"dbms-acid-1", "topic":"dbms", "difficulty":0.45, "prompt":"Which ACID property ensures committed data survives a crash?", "choices":["Atomicity", "Consistency", "Isolation", "Durability"], "answer":3, "explanation":"Durability preserves committed transactions after failures."},
 {"id":"algo-big-o-1", "topic":"algorithms", "difficulty":0.50, "prompt":"What is the time complexity of binary search over a sorted array?", "choices":["O(1)", "O(log n)", "O(n)", "O(n log n)"], "answer":1, "explanation":"Each comparison halves the remaining search interval."},
 {"id":"net-tcp-1", "topic":"computer_networks", "difficulty":0.45, "prompt":"TCP primarily provides which service?", "choices":["Best-effort datagrams", "Reliable ordered byte stream", "Only encryption", "Only routing"], "answer":1, "explanation":"TCP provides reliable, ordered delivery to applications."},
]

def conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c

def init_db() -> None:
    c=conn(); c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS profiles(user_id INTEGER PRIMARY KEY REFERENCES users(id), target_exam TEXT NOT NULL DEFAULT 'GATE CSE', stage TEXT, hours_per_week INTEGER, target_score TEXT, preferences TEXT DEFAULT '{}', updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS topic_states(user_id INTEGER REFERENCES users(id), topic TEXT, mastery REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0, last_mistake TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,topic));
    CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), version INTEGER, rationale TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS plan_items(id INTEGER PRIMARY KEY, plan_id INTEGER REFERENCES plans(id), topic TEXT, week INTEGER, hours REAL, focus TEXT);
    CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), question_id TEXT, topic TEXT, selected INTEGER, correct INTEGER, diagnosis TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), role TEXT, content TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    '''); c.commit(); c.close()

def hash_password(password: str) -> str:
    salt=os.urandom(16); digest=hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310000)
    return base64.b64encode(salt+digest).decode()
def verify_password(password: str, stored: str) -> bool:
    raw=base64.b64decode(stored); return hmac.compare_digest(raw[16:], hashlib.pbkdf2_hmac('sha256', password.encode(), raw[:16], 310000))
def token(user_id:int) -> str:
    payload=base64.urlsafe_b64encode(json.dumps({"sub":user_id,"exp":int(time.time())+86400}).encode()).decode().rstrip('=')
    sig=hmac.new(SECRET.encode(),payload.encode(),hashlib.sha256).hexdigest(); return payload+'.'+sig
def user_from_token(value:str|None)->int|None:
    try:
        payload,sig=(value or '').split('.'); expected=hmac.new(SECRET.encode(),payload.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected): return None
        data=json.loads(base64.urlsafe_b64decode(payload+'===')); return int(data['sub']) if data['exp']>=time.time() else None
    except Exception: return None

def seed_states(user_id:int) -> None:
    c=conn()
    for key, topic in TOPICS.items(): c.execute("INSERT OR IGNORE INTO topic_states(user_id,topic,mastery) VALUES(?,?,?)",(user_id,key,topic['baseline']))
    c.commit(); c.close()
def profile(user_id:int)->dict[str,Any]:
    c=conn(); p=c.execute("SELECT * FROM profiles WHERE user_id=?",(user_id,)).fetchone(); states=[dict(x) for x in c.execute("SELECT * FROM topic_states WHERE user_id=? ORDER BY mastery",(user_id,))]; c.close()
    return {"profile":dict(p) if p else None,"topics":states}
def build_plan(user_id:int)->dict[str,Any]:
    data=profile(user_id); p=data['profile'] or {}; hours=max(2,int(p.get('hours_per_week') or 8)); topics=data['topics']; weakest=sorted(topics,key=lambda x:x['mastery'])
    c=conn(); version=(c.execute("SELECT COALESCE(MAX(version),0)+1 FROM plans WHERE user_id=?",(user_id,)).fetchone()[0]); rationale=f"Version {version} prioritizes observed low mastery and reserves 25% of {hours} weekly hours for retrieval practice and review."
    cur=c.execute("INSERT INTO plans(user_id,version,rationale) VALUES(?,?,?)",(user_id,version,rationale)); pid=cur.lastrowid
    items=[]
    for i,state in enumerate(weakest):
        allocation=round(hours*(0.35 if i==0 else 0.25 if i==1 else 0.15),1); item={"week":1,"topic":state['topic'],"hours":allocation,"focus":"learn concepts, then complete the recommended practice"}; items.append(item); c.execute("INSERT INTO plan_items(plan_id,topic,week,hours,focus) VALUES(?,?,?,?,?)",(pid,item['topic'],item['week'],item['hours'],item['focus']))
    c.commit(); c.close(); return {"version":version,"rationale":rationale,"items":items}
def practice(user_id:int, topic:str|None)->list[dict[str,Any]]:
    states={x['topic']:x for x in profile(user_id)['topics']}; chosen=topic or min(states,key=lambda key:states[key]['mastery'])
    return [{k:v for k,v in q.items() if k not in ('answer','explanation')} for q in QUESTIONS if q['topic']==chosen]
def evaluate(user_id:int, question_id:str, selected:int, elapsed_seconds:int|None)->dict[str,Any]:
    q=next((q for q in QUESTIONS if q['id']==question_id),None)
    if not q: raise ValueError("Unknown question")
    correct=selected==q['answer']; diagnosis="correct" if correct else ("time-management issue" if elapsed_seconds and elapsed_seconds>120 else "conceptual misunderstanding")
    c=conn(); state=c.execute("SELECT mastery,attempts,correct FROM topic_states WHERE user_id=? AND topic=?",(user_id,q['topic'])).fetchone(); attempts=state['attempts']+1; correct_count=state['correct']+int(correct); observed=correct_count/attempts; mastery=round(max(.05,min(.95,.65*state['mastery']+.35*observed)),2)
    c.execute("UPDATE topic_states SET mastery=?,attempts=?,correct=?,last_mistake=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND topic=?",(mastery,attempts,correct_count,None if correct else diagnosis,user_id,q['topic']))
    c.execute("INSERT INTO attempts(user_id,question_id,topic,selected,correct,diagnosis) VALUES(?,?,?,?,?,?)",(user_id,question_id,q['topic'],selected,int(correct),diagnosis)); c.commit(); c.close()
    recommendation=("Increase difficulty slightly and schedule a short recall review." if correct else f"Revisit {TOPICS[q['topic']]['name']} fundamentals, then retry a comparable question.")
    return {"correct":correct,"diagnosis":diagnosis,"explanation":q['explanation'],"mastery":mastery,"recommendation":recommendation}
def mentor(user_id:int, message:str)->dict[str,Any]:
    lowered=message.lower(); topic=next((k for k,v in TOPICS.items() if any(word in lowered for word in v['keywords'])),None)
    if "deadlock" in lowered: answer="Deadlock is a state where processes wait indefinitely for resources held by one another. Check the four necessary conditions: mutual exclusion, hold-and-wait, no preemption, and circular wait. Which condition could your system break?"
    elif topic: answer=f"Let's work on {TOPICS[topic]['name']}. Start by stating the core idea in your own words; I will use that to choose the next explanation or practice question."
    else: answer="I can tutor GATE CSE topics, create practice, explain your evidence-based weak areas, or help research source-grounded exam information. Name a topic to begin."
    c=conn(); c.execute("INSERT INTO messages(user_id,role,content) VALUES(?,?,?)",(user_id,'user',message)); c.execute("INSERT INTO messages(user_id,role,content) VALUES(?,?,?)",(user_id,'assistant',answer)); c.commit(); c.close(); return {"answer":answer,"topic":topic,"grounding":"Conceptual tutoring uses the curated MVP knowledge pack; it does not claim current exam-policy facts."}
def research(query:str)->dict[str,Any]:
    return {"answer":"For current GATE CSE policy, consult the official GATE website. PrepPilot records this as an official source but does not infer a date-sensitive rule from unavailable verified text.","sources":SOURCES,"confidence":"limited","warning":"Live web retrieval is intentionally not enabled in this offline MVP; verify current dates, eligibility, pattern, and syllabus at the linked official source."}
