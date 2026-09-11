let token=localStorage.token; const out=document.querySelector('#output');
function show(x){out.textContent=JSON.stringify(x,null,2)}
async function api(path,method='GET',data){let r=await fetch(path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:data?JSON.stringify(data):undefined});let x=await r.json();if(!r.ok)throw Error(x.detail);return x}
async function signup(){try{let x=await api('/api/auth/signup','POST',{email:email.value,password:password.value}); token=localStorage.token=x.token; ready()}catch(e){status.textContent=e.message}}
async function login(){try{let x=await api('/api/auth/login','POST',{email:email.value,password:password.value});token=localStorage.token=x.token;ready()}catch(e){status.textContent=e.message}}
function ready(){auth.hidden=true;app.hidden=false;status.textContent=''}
async function onboard(){show(await api('/api/onboarding','PUT',{hours_per_week:+hours.value,stage:'beginner',preferences:{mode:'concept-first'}}))}
async function plan(){show(await api('/api/plans/generate','POST',{}))}
async function mentor(){show(await api('/api/mentor','POST',{message:message.value}))}
async function practice(){show(await api('/api/practice'))}
async function research(){show(await api('/api/research?q=GATE+CSE+syllabus'))}
if(token)ready();
