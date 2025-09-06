// ==== helpers & state ====
const $ = s => document.querySelector(s);
const apikeyInput = $('#apikey');
const saveKeyBtn  = $('#saveKey');
const apikeyRow   = $('#apikeyRow');
const whoRow      = $('#whoRow');
const whoSpan     = $('#who');
const logoutBtn   = $('#logout');

const autoModelCb = $('#autoModel');
const modelSel    = $('#model');
const memoryRadios= document.getElementsByName('memory');
const fileInput   = $('#file');
const websearchCb = $('#websearch');

const sendBtn     = $('#send');
const downloadA   = $('#download');
const promptTa    = $('#prompt');
const messagesEl  = $('#messages');
const newChatBtn  = $('#newChat');
const logo        = $('#logo');
const busyDot     = $('#busy');
const debugPre    = $('#debug');
const ctxPre      = $('#context');

const API_BASE = ''; // stejný původ; /ask a /v1/chat obstará FastAPI
const STORAGE_NS = 'fura-ui';
const TTL_DAYS = 7;

let attachedText = '';
let history = loadHistory();

// ==== storage ====
function lsGet(k, def=null){ try{ const v = localStorage.getItem(`${STORAGE_NS}:${k}`); return v===null?def:JSON.parse(v);}catch{ return def; } }
function lsSet(k, v){ localStorage.setItem(`${STORAGE_NS}:${k}`, JSON.stringify(v)); }
function lsDel(k){ localStorage.removeItem(`${STORAGE_NS}:${k}`); }

function loadHistory(){
  const now = Date.now();
  const all = lsGet('history', []);
  const fresh = all.filter(x => (now - x.ts) < TTL_DAYS*24*3600*1000);
  if (fresh.length !== all.length) lsSet('history', fresh);
  return fresh;
}
function pushHistory(role, content){
  history.push({ts: Date.now(), role, content});
  lsSet('history', history);
}

// ==== UI init ====
function renderMessages(){
  messagesEl.innerHTML = '';
  for(const m of history){
    const div = document.createElement('div');
    div.className = `bubble ${m.role==='user'?'user':'ai'}`;
    div.innerHTML = `<span class="role">${m.role==='user'?'Ty':'AI'}</span><pre>${escapeHtml(m.content)}</pre>`;
    messagesEl.appendChild(div);
  }
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(s){
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function setBusy(on){
  logo.classList.toggle('spin', on);
  busyDot.style.opacity = on ? '1' : '.6';
  sendBtn.disabled = on;
}

function currentMemory(){
  for(const r of memoryRadios){ if (r.checked) return r.value; }
  return 'public';
}

function applyPrefs(){
  const savedKey = lsGet('apikey', '');
  if (savedKey){
    apikeyRow.classList.add('hidden');
    whoRow.classList.remove('hidden');
    whoSpan.textContent = 'přihlášen';
  }else{
    apikeyRow.classList.remove('hidden');
    whoRow.classList.add('hidden');
  }
  const savedAuto = lsGet('autoModel', true);
  autoModelCb.checked = !!savedAuto;
  modelSel.disabled = !!savedAuto;
  const savedModel = lsGet('model', 'llama3:8b');
  modelSel.value = savedModel;

  const savedMem = lsGet('memory', 'public');
  for(const r of memoryRadios){ r.checked = (r.value === savedMem); }

  const savedWs = lsGet('websearch', false);
  websearchCb.checked = !!savedWs;

  renderMessages();
  updateContextPreview();
}

function updateContextPreview(){
  const lines = [];
  lines.push(`Paměť: ${currentMemory()}`);
  lines.push(`Websearch: ${websearchCb.checked ? 'zapnutý' : 'vypnutý'}`);
  lines.push(`Model: ${autoModelCb.checked ? 'auto' : modelSel.value}`);
  if (attachedText) lines.push(`Přiložený TXT: ${attachedText.length} znaků`);
  ctxPre.textContent = lines.join('\n');
}

// ==== events ====
saveKeyBtn.addEventListener('click', () => {
  const k = (apikeyInput.value || '').trim();
  if (!k){ return; }
  lsSet('apikey', k);
  apikeyInput.value = '';
  applyPrefs();
});

logoutBtn.addEventListener('click', () => {
  lsDel('apikey');
  applyPrefs();
});

autoModelCb.addEventListener('change', () => {
  lsSet('autoModel', autoModelCb.checked);
  modelSel.disabled = autoModelCb.checked;
  updateContextPreview();
});
modelSel.addEventListener('change', () => {
  lsSet('model', modelSel.value);
  updateContextPreview();
});
for(const r of memoryRadios){
  r.addEventListener('change', ()=>{
    lsSet('memory', currentMemory());
    updateContextPreview();
  });
}
websearchCb.addEventListener('change', () => {
  lsSet('websearch', websearchCb.checked);
  updateContextPreview();
});

fileInput.addEventListener('change', async (ev) => {
  attachedText = '';
  const f = ev.target.files?.[0];
  if (!f) return;
  if (!/^text\/plain|\.txt$/i.test(f.type) && !/\.txt$/i.test(f.name)){
    debug(`Soubor nevypadá jako TXT: ${f.name}`);
    return;
  }
  const txt = await f.text();
  attachedText = txt;
  updateContextPreview();
});

promptTa.addEventListener('keydown', (e)=>{
  if (e.key==='Enter' && !e.shiftKey){
    e.preventDefault();
    sendBtn.click();
  }
});

newChatBtn.addEventListener('click', () => {
  history = [];
  lsSet('history', history);
  downloadA.classList.add('hidden');
  renderMessages();
});

sendBtn.addEventListener('click', sendMessage);

// ==== networking ====
async function sendMessage(){
  const text = (promptTa.value || '').trim();
  if (!text) return;

  // lokální UI aktualizace
  pushHistory('user', text + (attachedText ? `\n\n[Příloha TXT]\n${attachedText}` : ''));
  renderMessages();
  promptTa.value = '';
  downloadA.classList.add('hidden');

  setBusy(true);
  debug('(odesílám dotaz…)');

  // request payload
  const payload = {
    messages: [{ role: 'user', content: composePrompt(text) }],
    temperature: 0.7
  };

  // model
  const auto = lsGet('autoModel', true);
  if (!auto){
    payload.model = lsGet('model', 'llama3:8b');
  }
  // doplňme volitelné meta pro budoucno (backend je zatím ignoruje)
  payload.memory_scope = currentMemory();
  payload.websearch = !!lsGet('websearch', false);

  // endpoint – OpenAI-like
  const url = `${API_BASE}/v1/chat`;

  const headers = {
    'Content-Type': 'application/json'
  };
  const k = lsGet('apikey', '');
  if (k) headers['X-API-Key'] = k;

  try{
    const res = await fetch(url, { method:'POST', headers, body: JSON.stringify(payload) });
    const body = await safeJson(res);
    if (!res.ok){
      const msg = (typeof body === 'object' ? (body.detail||body.error||JSON.stringify(body)) : await res.text());
      throw new Error(msg);
    }
    const answer = (body && body.answer) ? body.answer : '(prázdná odpověď)';
    pushHistory('assistant', answer);
    renderMessages();
    updateDownload(answer);
    debug('OK');
  }catch(err){
    const msg = (err && err.message) ? err.message : String(err);
    pushHistory('assistant', `❌ Chyba: ${msg}`);
    renderMessages();
    debug(`Chyba: ${msg}`);
  }finally{
    setBusy(false);
    attachedText = ''; // jednorázová příloha
    fileInput.value = '';
    updateContextPreview();
  }
}

function composePrompt(text){
  if (!attachedText) return text;
  return `${text}\n\n---\nPřiložený soubor (text):\n${attachedText}`;
}

async function safeJson(res){
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return await res.json();
  return await res.text();
}

function updateDownload(answer){
  const blob = new Blob([answer], {type:'text/plain;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  downloadA.href = url;
  downloadA.classList.remove('hidden');
}

function debug(msg){
  const now = new Date().toLocaleTimeString();
  debugPre.textContent = `[${now}] ${msg}\n` + debugPre.textContent;
}

// ==== start ====
applyPrefs();