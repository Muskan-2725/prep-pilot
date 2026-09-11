import json
from io import BytesIO
from app import core
from app.server import app

def call(path, method='GET', data=None, token=None):
    raw=json.dumps(data or {}).encode(); captured={}
    def start(status, headers): captured.update(status=status,headers=headers)
    env={'REQUEST_METHOD':method,'PATH_INFO':path,'QUERY_STRING':'','wsgi.input':BytesIO(raw),'CONTENT_LENGTH':str(len(raw))}
    if token: env['HTTP_AUTHORIZATION']='Bearer '+token
    result=json.loads(b''.join(app(env,start))); return captured['status'],result

def test_full_learning_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(core,'DB_PATH',tmp_path/'test.db'); monkeypatch.setattr(core,'DATA_DIR',tmp_path)
    status, account=call('/api/auth/signup','POST',{'email':'student@example.com','password':'secure-pass-123'})
    assert status.startswith('201'); token=account['token']
    assert call('/api/onboarding','PUT',{'hours_per_week':8,'stage':'beginner'},token)[0].startswith('200')
    status, plan=call('/api/plans/generate','POST',{},token); assert status.startswith('201') and plan['items']
    status, reply=call('/api/mentor','POST',{'message':"I don't understand deadlocks"},token); assert 'four necessary conditions' in reply['answer']
    _, questions=call('/api/practice','GET',None,token); q=questions['questions'][0]
    status, evaluation=call('/api/attempts','POST',{'question_id':q['id'],'selected':0},token)
    assert status.startswith('201') and evaluation['diagnosis']=='conceptual misunderstanding'
    _, profile=call('/api/profile','GET',None,token); assert any(x['attempts']==1 for x in profile['topics'])

def test_research_is_explicitly_limited(tmp_path, monkeypatch):
    monkeypatch.setattr(core,'DB_PATH',tmp_path/'test.db'); monkeypatch.setattr(core,'DATA_DIR',tmp_path)
    _, a=call('/api/auth/signup','POST',{'email':'source@example.com','password':'secure-pass-123'})
    _, result=call('/api/research','GET',None,a['token']); assert result['confidence']=='limited' and result['sources'][0]['quality']=='official'
