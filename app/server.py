"""Standard-library WSGI API for PrepPilot V1."""
from __future__ import annotations
import json, logging, mimetypes
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from . import core
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
STATIC=Path(__file__).parents[1]/"static"
def respond(start,status,payload,headers=()):
 raw=json.dumps(payload,default=str).encode(); start(status,[("Content-Type","application/json; charset=utf-8"),("Content-Length",str(len(raw))),*(headers or ())]); return [raw]
def parse_body(env):
 length=int(env.get("CONTENT_LENGTH") or 0)
 if length>100_000: raise ValueError("Request body is too large.")
 try: return json.loads(env["wsgi.input"].read(length) or "{}")
 except json.JSONDecodeError: raise ValueError("Body must be valid JSON.")
def auth(env):
 uid=core.user_from_token(env.get("HTTP_AUTHORIZATION","").removeprefix("Bearer ").strip())
 if not uid: raise PermissionError("Authentication required.")
 return uid
def app(env,start):
 core.init_db(); path,method=env["PATH_INFO"],env["REQUEST_METHOD"]
 try:
  if path=="/" and method=="GET":
   raw=(STATIC/"index.html").read_bytes(); start("200 OK",[("Content-Type","text/html; charset=utf-8"),("Content-Length",str(len(raw)))]); return [raw]
  if path.startswith("/static/") and method=="GET":
   file=(STATIC/path.removeprefix("/static/")).resolve()
   if STATIC.resolve() not in file.parents or not file.is_file(): return respond(start,"404 Not Found",{"detail":"Not found."})
   raw=file.read_bytes(); start("200 OK",[("Content-Type",mimetypes.guess_type(str(file))[0] or "application/octet-stream"),("Content-Length",str(len(raw)))]); return [raw]
  if path=="/health": return respond(start,"200 OK",{"status":"ok"})
  if path=="/api/auth/signup" and method=="POST":
   d=parse_body(env); email=str(d.get("email","")).strip().lower(); password=str(d.get("password",""))
   if "@" not in email or len(password)<10: return respond(start,"422 Unprocessable Entity",{"detail":"Use a valid email and a 10+ character password."})
   try: uid=core.create_user(email,password)
   except __import__('sqlite3').IntegrityError: return respond(start,"409 Conflict",{"detail":"Email already registered."})
   return respond(start,"201 Created",{"token":core.token(uid),"user":{"id":uid,"email":email}})
  if path=="/api/auth/login" and method=="POST":
   d=parse_body(env)
   with core.conn() as c: row=c.execute("SELECT * FROM users WHERE email=?",(str(d.get("email","")).lower(),)).fetchone()
   if not row or not core.verify_password(str(d.get("password","")),row["password_hash"]): return respond(start,"401 Unauthorized",{"detail":"Invalid email or password."})
   return respond(start,"200 OK",{"token":core.token(row["id"]),"user":{"id":row["id"],"email":row["email"]}})
  uid=auth(env); query=parse_qs(env.get("QUERY_STRING", ""))
  if path=="/api/onboarding" and method=="PUT": return respond(start,"200 OK",core.onboarding(uid,parse_body(env)))
  if path=="/api/dashboard" and method=="GET": return respond(start,"200 OK",core.dashboard(uid))
  if path=="/api/profile" and method=="GET": return respond(start,"200 OK",core.dashboard(uid))
  if path=="/api/plans/generate" and method=="POST": return respond(start,"201 Created",core.build_plan(uid))
  if path=="/api/practice" and method=="GET": return respond(start,"200 OK",{"questions":core.practice(uid,query.get("topic",[None])[0],query.get("difficulty",[None])[0],query.get("count",[1])[0])})
  if path=="/api/attempts" and method=="POST": return respond(start,"201 Created",core.evaluate(uid,parse_body(env)))
  if path=="/api/mentor" and method=="POST": return respond(start,"200 OK",core.mentor(uid,str(parse_body(env).get("message", ""))[:2000]))
  if path=="/api/research" and method=="GET": return respond(start,"200 OK",core.research(query.get("q",[""])[0]))
  return respond(start,"404 Not Found",{"detail":"Not found."})
 except PermissionError as e: return respond(start,"401 Unauthorized",{"detail":str(e)})
 except (ValueError,KeyError,TypeError) as e: return respond(start,"422 Unprocessable Entity",{"detail":str(e)})
 except Exception:
  logging.exception("request failure %s",path); return respond(start,"500 Internal Server Error",{"detail":"Unexpected server error."})
def main():
 core.init_db(); print("PrepPilot V1: http://127.0.0.1:8000"); make_server("127.0.0.1",8000,app).serve_forever()
if __name__=="__main__": main()
