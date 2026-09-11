"""Standard-library WSGI HTTP API and static UI for the PrepPilot MVP."""
from __future__ import annotations
import json, logging, mimetypes
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from . import core
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
STATIC=Path(__file__).parents[1]/'static'
def response(start, status, data, headers=None):
    raw=json.dumps(data).encode(); start(status,[('Content-Type','application/json'),('Content-Length',str(len(raw))),* (headers or [])]); return [raw]
def body(env):
    try: return json.loads(env['wsgi.input'].read(int(env.get('CONTENT_LENGTH') or 0)) or '{}')
    except json.JSONDecodeError: raise ValueError('Body must be valid JSON')
def user(env):
    value=env.get('HTTP_AUTHORIZATION','').removeprefix('Bearer ').strip(); uid=core.user_from_token(value)
    if not uid: raise PermissionError('Authentication required')
    return uid
def app(env,start):
    core.init_db(); path=env['PATH_INFO']; method=env['REQUEST_METHOD']
    try:
      if path=='/' and method=='GET':
        raw=(STATIC/'index.html').read_bytes(); start('200 OK',[('Content-Type','text/html; charset=utf-8'),('Content-Length',str(len(raw)))]); return [raw]
      if path.startswith('/static/') and method=='GET':
        f=(STATIC/path.removeprefix('/static/')).resolve()
        if STATIC.resolve() not in f.parents or not f.is_file(): return response(start,'404 Not Found',{'detail':'Not found'})
        raw=f.read_bytes(); start('200 OK',[('Content-Type',mimetypes.guess_type(str(f))[0] or 'application/octet-stream'),('Content-Length',str(len(raw)))]); return [raw]
      if path=='/health': return response(start,'200 OK',{'status':'ok'})
      if path=='/api/auth/signup' and method=='POST':
        d=body(env); email=str(d.get('email','')).strip().lower(); password=str(d.get('password',''))
        if '@' not in email or len(password)<10: return response(start,'422 Unprocessable Entity',{'detail':'Use a valid email and password of at least 10 characters.'})
        c=core.conn()
        try: uid=c.execute('INSERT INTO users(email,password_hash) VALUES(?,?)',(email,core.hash_password(password))).lastrowid; c.commit()
        except Exception: return response(start,'409 Conflict',{'detail':'Email already registered.'})
        finally: c.close()
        core.seed_states(uid); return response(start,'201 Created',{'token':core.token(uid),'user':{'id':uid,'email':email}})
      if path=='/api/auth/login' and method=='POST':
        d=body(env); c=core.conn(); row=c.execute('SELECT * FROM users WHERE email=?',(str(d.get('email','')).lower(),)).fetchone(); c.close()
        if not row or not core.verify_password(str(d.get('password','')),row['password_hash']): return response(start,'401 Unauthorized',{'detail':'Invalid email or password.'})
        return response(start,'200 OK',{'token':core.token(row['id']),'user':{'id':row['id'],'email':row['email']}})
      uid=user(env)
      if path=='/api/onboarding' and method=='PUT':
        d=body(env); hours=int(d.get('hours_per_week',8));
        if not 2<=hours<=80: return response(start,'422 Unprocessable Entity',{'detail':'hours_per_week must be between 2 and 80.'})
        c=core.conn(); c.execute("INSERT INTO profiles(user_id,target_exam,stage,hours_per_week,target_score,preferences) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET stage=excluded.stage,hours_per_week=excluded.hours_per_week,target_score=excluded.target_score,preferences=excluded.preferences,updated_at=CURRENT_TIMESTAMP",(uid,'GATE CSE',d.get('stage','beginner'),hours,d.get('target_score',''),json.dumps(d.get('preferences',{})))); c.commit(); c.close(); return response(start,'200 OK',core.profile(uid))
      if path=='/api/profile' and method=='GET': return response(start,'200 OK',core.profile(uid))
      if path=='/api/plans/generate' and method=='POST': return response(start,'201 Created',core.build_plan(uid))
      if path=='/api/practice' and method=='GET': return response(start,'200 OK',{'questions':core.practice(uid,parse_qs(env.get('QUERY_STRING','')).get('topic',[None])[0])})
      if path=='/api/attempts' and method=='POST':
        d=body(env); return response(start,'201 Created',core.evaluate(uid,str(d.get('question_id','')),int(d.get('selected')),d.get('elapsed_seconds')))
      if path=='/api/mentor' and method=='POST': return response(start,'200 OK',core.mentor(uid,str(body(env).get('message',''))[:2000]))
      if path=='/api/research' and method=='GET': return response(start,'200 OK',core.research(parse_qs(env.get('QUERY_STRING','')).get('q',[''])[0]))
      return response(start,'404 Not Found',{'detail':'Not found'})
    except PermissionError as exc: return response(start,'401 Unauthorized',{'detail':str(exc)})
    except (ValueError,TypeError) as exc: return response(start,'422 Unprocessable Entity',{'detail':str(exc)})
    except Exception:
      logging.exception('request failed path=%s',path); return response(start,'500 Internal Server Error',{'detail':'Unexpected server error'})
def main():
    core.init_db(); print('PrepPilot at http://127.0.0.1:8000'); make_server('127.0.0.1',8000,app).serve_forever()
if __name__=='__main__': main()
