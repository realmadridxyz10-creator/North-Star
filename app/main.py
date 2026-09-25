from fastapi import FastAPI, Query, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pathlib import Path
from html import escape
import json, re, os, sqlite3, time, secrets, hmac, hashlib, base64, uuid
from urllib.parse import quote_plus
from pydantic import BaseModel, Field
from app.external_llm import ProviderNeutralLLMAdapter, load_llm_config, safe_external_synthesis
from app.openai_transport import OpenAIResponsesTransport, stdlib_http_post
from app.groq_transport import GroqChatTransport

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
RELEASE='NS-DP-MVP-RUNTIME-DEV-006'

MODULES=[
    ('Foundation','foundation','Build the common language, concepts and mental models for enterprise technology.'),
    ('Professional','professional','Apply, design, improve and govern enterprise technology disciplines in practice.'),
    ('Executive','executive','Make integrated enterprise decisions across strategy, architecture, delivery, risk and value.'),
    ('Leadership','leadership','Shape purpose, culture, people, influence and enduring organizational capability.')
]
MODULE_BY_SLUG={slug:name for name,slug,_ in MODULES}
SLUG_BY_MODULE={name:slug for name,slug,_ in MODULES}

DIMENSIONS=[
    'UNDERSTAND','GOVERN','DESIGN','TRANSFORM','BUILD','DELIVER','RUN','PROTECT','OPTIMIZE','LEAD','EVOLVE'
]
DIMENSION_DESCRIPTIONS={
    'UNDERSTAND':'Context, needs, evidence and enterprise perspective.',
    'GOVERN':'Accountability, controls, policy, assurance and decision rights.',
    'DESIGN':'Architecture, structure, principles and intentional solution design.',
    'TRANSFORM':'Change, modernization, adoption and enterprise transformation.',
    'BUILD':'Creation, engineering, implementation and capability development.',
    'DELIVER':'Portfolio, programme, project and outcome delivery.',
    'RUN':'Service, operations, reliability and day-to-day performance.',
    'PROTECT':'Cybersecurity, risk, resilience, privacy and continuity.',
    'OPTIMIZE':'Measurement, efficiency, improvement and value realization.',
    'LEAD':'People, influence, judgment, culture and executive leadership.',
    'EVOLVE':'Learning, renewal, innovation and enduring capability.'
}


def load_jsonl(name):
    with open(DATA/name,encoding='utf-8') as f:
        return [json.loads(x) for x in f if x.strip()]

def load_json(name):
    with open(DATA/name,encoding='utf-8') as f:
        return json.load(f)

SEARCH=load_jsonl('search_records.jsonl')
CHUNKS=load_jsonl('retrieval_chunks.jsonl')
CHAPTER_REGISTRY=load_json('B1_D04_chapter_route_registry.json')

# Pre-index content by module/chapter from canonical IDs (CH-F0-KB001 etc.)
CHAPTER_CONTENT={}
for r in SEARCH:
    cid=r.get('canonical_id','')
    m=re.match(r'CH-([A-Z]+\d+)-KB\d+',cid)
    if not m:
        m=re.match(r'NS-E-(E\d+)-S\d+',cid)
    if not m:
        continue
    chapter=m.group(1)
    module=r.get('module')
    CHAPTER_CONTENT.setdefault((module,chapter),[]).append(r)
for key,items in CHAPTER_CONTENT.items():
    items.sort(key=lambda x:x.get('canonical_id',''))

SEARCH_BY_ID={r.get('canonical_id'):r for r in SEARCH if r.get('canonical_id')}
DIMENSION_RECORDS={d:[] for d in DIMENSIONS}
for r in SEARCH:
    for d in r.get('dimension_tags',[]) or []:
        if d in DIMENSION_RECORDS:
            DIMENSION_RECORDS[d].append(r)

def chapter_from_record(r):
    cid=r.get('canonical_id','')
    m=re.match(r'CH-([A-Z]+\d+)-KB\d+',cid) or re.match(r'NS-E-(E\d+)-S\d+',cid)
    return m.group(1) if m else None

def chapter_route(module,code):
    slug=SLUG_BY_MODULE.get(module,'')
    return f'/modules/{slug}/chapters/{code.lower()}' if slug and code else ''

def dimension_counts():
    return {d:len(DIMENSION_RECORDS[d]) for d in DIMENSIONS}

def build_compass(canonical_id=None,dimension=None,module=None,chapter=None,limit=60):
    if dimension:
        dimension=dimension.upper()
        if dimension not in DIMENSIONS:
            raise HTTPException(400,'unknown_dimension')
    anchor=SEARCH_BY_ID.get(canonical_id) if canonical_id else None
    if canonical_id and not anchor:
        raise HTTPException(404,'canonical_id_not_found')
    if anchor:
        module=module or anchor.get('module')
        chapter=chapter or chapter_from_record(anchor)
        if not dimension:
            tags=anchor.get('dimension_tags') or []
            dimension=tags[0] if tags else None
    candidates=list(SEARCH)
    if dimension:
        candidates=[r for r in candidates if dimension in (r.get('dimension_tags') or [])]
    if module:
        candidates=[r for r in candidates if (r.get('module') or '').lower()==module.lower()]
    if chapter:
        candidates=[r for r in candidates if (chapter_from_record(r) or '').lower()==chapter.lower()]
    candidates=candidates[:max(1,min(limit,200))]
    nodes=[]; edges=[]; seen=set()
    for r in candidates:
        cid=r.get('canonical_id')
        if not cid or cid in seen: continue
        seen.add(cid)
        code=chapter_from_record(r)
        nodes.append({'id':cid,'type':'content','label':r.get('title') or r.get('text','')[:90],
                      'route':normalize_route(r),'meta':{'module':r.get('module'),'chapter':code,'dimensions':r.get('dimension_tags') or []}})
        for d in r.get('dimension_tags') or []:
            if d in DIMENSIONS:
                did=f'DIM-{d}'
                if did not in seen:
                    seen.add(did); nodes.append({'id':did,'type':'dimension','label':d,'route':f'/compass?dimension={d}','meta':{}})
                edges.append({'from':cid,'to':did,'relationship':'governed_dimension_tag','authority':'B1 dimension_tags'})
    # Mechanical sequence edges only within the returned chapter-bounded view.
    by_chapter={}
    for r in candidates:
        key=(r.get('module'),chapter_from_record(r))
        by_chapter.setdefault(key,[]).append(r)
    for key,items in by_chapter.items():
        items=sorted(items,key=lambda x:x.get('canonical_id',''))
        for a,b in zip(items,items[1:]):
            edges.append({'from':a.get('canonical_id'),'to':b.get('canonical_id'),'relationship':'chapter_sequence','authority':'canonical hierarchy/order'})
    return {'release':RELEASE,'source_release_identity':'R4/B1','filters':{'canonical_id':canonical_id,'dimension':dimension,'module':module,'chapter':chapter},
            'dimension_counts':dimension_counts(),'result_count':len(candidates),'nodes':nodes,'edges':edges,
            'governance':{'canonical_relationships_only':True,'inferred_similarity_edges':False,
                          'rule':'Only governed B1 metadata and mechanical hierarchy/sequence are represented; no inferred relationships are created.'}}

# DEV-004: grounded AI runtime. Provider-neutral contract; local deterministic evidence composer.
AI_PROVIDER='LOCAL_EVIDENCE'


def build_external_llm_adapter():
    config=load_llm_config()
    if not config.external_requested:
        return ProviderNeutralLLMAdapter(config)
    provider=config.provider.upper()
    if provider=='OPENAI':
        api_key=(os.environ.get('OPENAI_API_KEY') or '').strip()
        if not api_key or not config.model:
            return ProviderNeutralLLMAdapter(config)
        transport=OpenAIResponsesTransport(api_key,config.model,stdlib_http_post)
        return ProviderNeutralLLMAdapter(config,transport)
    if provider=='GROQ':
        api_key=(os.environ.get('GROQ_API_KEY') or '').strip()
        if not api_key or not config.model:
            return ProviderNeutralLLMAdapter(config)
        transport=GroqChatTransport(api_key,config.model,stdlib_http_post)
        return ProviderNeutralLLMAdapter(config,transport)
    return ProviderNeutralLLMAdapter(config)


EXTERNAL_LLM_ADAPTER=build_external_llm_adapter()
CHUNK_BY_ID={c.get('chunk_id'):c for c in CHUNKS if c.get('chunk_id')}

def tokenize(q):
    return [t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-/]+",(q or '').lower()) if len(t)>2]

def classify_question(q):
    x=(q or '').lower()
    if any(p in x for p in ['ignore previous','ignore all','system prompt','developer message','override governance','bypass','jailbreak']): return 'policy_attack'
    if any(p in x for p in ['where is','where can i find','which chapter','navigate','take me to']): return 'canonical_navigation'
    if any(p in x for p in ['compare','difference between','versus',' vs ','contrast']): return 'grounded_comparison'
    if any(p in x for p in ['what should','how should','decision','recommend','choose','prioritize']): return 'decision_support'
    return 'grounded_explanation'

def retrieve_evidence(q,limit=6):
    toks=tokenize(q)
    if not toks: return []
    scored=[]
    for c in CHUNKS:
        hay=' '.join(str(c.get(k,'')) for k in ['title','heading','text','module','chapter']).lower()
        score=sum((3 if t in str(c.get('title','')).lower() else 1)*hay.count(t) for t in toks)
        if score: scored.append((score,c))
    scored.sort(key=lambda x:(-x[0],x[1].get('chunk_id','')))
    return [c for _,c in scored[:limit]]

def citation_from_chunk(c):
    module=c.get('module'); chapter=c.get('chapter')
    route=chapter_route(module,chapter) if module and chapter else c.get('route') or ''
    return {'chunk_id':c.get('chunk_id'),'canonical_id':c.get('canonical_id'),'title':c.get('title') or c.get('heading'),
            'module':module,'chapter':chapter,'source_locator':c.get('source_locator') or c.get('source') or c.get('chunk_id'),'route':route}

def compose_grounded_answer(q,answer_class,evidence):
    if not evidence:
        return 'I do not have sufficient governed North Star evidence to answer that question. Try a more specific North Star topic or use Search/Compass.'
    excerpts=[]
    for c in evidence[:3]:
        text=re.sub(r'\s+',' ',str(c.get('text',''))).strip()
        if text: excerpts.append(text[:420].rstrip())
    if answer_class=='canonical_navigation':
        c=evidence[0]; return f"The strongest governed match is {c.get('title') or c.get('heading') or c.get('chapter')}. Open the cited North Star location below."
    if answer_class=='grounded_comparison':
        return 'Grounded comparison from the retrieved North Star evidence:\n\n'+'\n\n'.join(f'• {x}' for x in excerpts[:2])
    if answer_class=='decision_support':
        return 'Decision support grounded in North Star:\n\n'+'\n\n'.join(f'• {x}' for x in excerpts[:3])+'\n\nUse these as governed inputs to judgment, not as an automated executive decision.'
    return 'North Star explains this through the following governed evidence:\n\n'+'\n\n'.join(excerpts[:3])

class AIAskRequest(BaseModel):
    question:str=Field(min_length=2,max_length=1200)
    max_evidence:int=Field(default=6,ge=1,le=10)

# DEV-005: identity, PayPal-first commerce contract and server-side entitlements.
IDENTITY_PROVIDER='LOCAL_OIDC_SIMULATOR'
PAYMENT_PROVIDER='PAYPAL_SIMULATOR'
SESSION_COOKIE='ns_session'
SESSION_SECRET=(os.environ.get('NS_SESSION_SECRET') or '').strip()
if not SESSION_SECRET:
    raise RuntimeError('NS_SESSION_SECRET is required')
DB_PATH=Path(os.environ.get('NS_DB_PATH') or (DATA/'runtime_dev.sqlite3'))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
PLANS={
    'preview':{'name':'Preview','price':'0.00','currency':'USD','entitlement':'preview','description':'Public orientation and selected governed content.'},
    'module':{'name':'Single Module','price':'29.00','currency':'USD','entitlement':'module','description':'One North Star level/module entitlement.'},
    'full':{'name':'Full Portal','price':'79.00','currency':'USD','entitlement':'full_portal','description':'Foundation through Leadership portal access.'},
    'premium_ai':{'name':'Premium AI','price':'99.00','currency':'USD','entitlement':'premium_ai','description':'Full portal plus governed AI assistance.'},
}

def db():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db(); c.executescript('''
    CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,display_name TEXT,provider TEXT NOT NULL,created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS entitlements(entitlement_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,entitlement_type TEXT NOT NULL,scope TEXT,status TEXT NOT NULL,source TEXT NOT NULL,source_ref TEXT,created_at INTEGER NOT NULL,UNIQUE(user_id,entitlement_type,scope,source_ref));
    CREATE TABLE IF NOT EXISTS orders(order_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,provider TEXT NOT NULL,provider_order_id TEXT UNIQUE NOT NULL,plan_code TEXT NOT NULL,amount TEXT NOT NULL,currency TEXT NOT NULL,status TEXT NOT NULL,idempotency_key TEXT UNIQUE NOT NULL,created_at INTEGER NOT NULL,captured_at INTEGER);
    CREATE TABLE IF NOT EXISTS audit_events(event_id TEXT PRIMARY KEY,user_id TEXT,event_type TEXT NOT NULL,detail TEXT NOT NULL,created_at INTEGER NOT NULL);
    '''); c.commit(); c.close()
init_db()

def b64u(b): return base64.urlsafe_b64encode(b).decode().rstrip('=')
def sign_session(payload):
    body=b64u(json.dumps(payload,separators=(',',':')).encode()); sig=b64u(hmac.new(SESSION_SECRET.encode(),body.encode(),hashlib.sha256).digest()); return body+'.'+sig
def read_session(token):
    try:
        body,sig=token.split('.',1); expected=b64u(hmac.new(SESSION_SECRET.encode(),body.encode(),hashlib.sha256).digest())
        if not hmac.compare_digest(sig,expected): return None
        payload=json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
        if payload.get('exp',0)<int(time.time()): return None
        return payload
    except Exception:return None

def current_user(request):
    token=request.cookies.get(SESSION_COOKIE); payload=read_session(token) if token else None
    if not payload:return None
    c=db(); row=c.execute('SELECT * FROM users WHERE user_id=?',(payload.get('sub'),)).fetchone(); c.close(); return dict(row) if row else None

def require_user(request):
    u=current_user(request)
    if not u: raise HTTPException(401,'authentication_required')
    return u

def audit(event_type,detail,user_id=None):
    c=db(); c.execute('INSERT INTO audit_events VALUES(?,?,?,?,?)',(str(uuid.uuid4()),user_id,event_type,json.dumps(detail,separators=(',',':')),int(time.time()))); c.commit(); c.close()

def effective_entitlements(user_id):
    c=db(); rows=c.execute("SELECT entitlement_type,scope,status,source,source_ref FROM entitlements WHERE user_id=? AND status='active' ORDER BY created_at",(user_id,)).fetchall(); c.close()
    vals=[dict(r) for r in rows]; types={r['entitlement_type'] for r in vals}
    return {'items':vals,'preview':True,'module':('module' in types or 'full_portal' in types or 'premium_ai' in types),'full_portal':('full_portal' in types or 'premium_ai' in types),'premium_ai':'premium_ai' in types}

def grant_entitlement(user_id,plan_code,source_ref):
    p=PLANS[plan_code]; et=p['entitlement']; scope='all' if et in ('full_portal','premium_ai') else ('selected_module' if et=='module' else 'public')
    c=db(); c.execute('INSERT OR IGNORE INTO entitlements VALUES(?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),user_id,et,scope,'active','paypal',source_ref,int(time.time()))); c.commit(); c.close()

class DevLoginRequest(BaseModel):
    email:str=Field(min_length=5,max_length=254)
    display_name:str=Field(default='North Star Reader',max_length=120)
class CreateOrderRequest(BaseModel):
    plan_code:str
    idempotency_key:str=Field(min_length=8,max_length=120)
class CaptureOrderRequest(BaseModel):
    provider_order_id:str

# --- Runtime routes ---
app=FastAPI(title='North Star Digital Portal DEV',version=RELEASE)

@app.middleware('http')
async def baseline_security_headers(request:Request,call_next):
    response=await call_next(request)
    response.headers.setdefault('X-Content-Type-Options','nosniff')
    response.headers.setdefault('X-Frame-Options','DENY')
    response.headers.setdefault('Referrer-Policy','strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy','camera=(), microphone=(), geolocation=()')
    response.headers.setdefault('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
    return response

@app.get('/api/health')
def health():
    return {'status':'ok','release':RELEASE,'environment':'LOCAL_DEV','search_records':len(SEARCH),'retrieval_chunks':len(CHUNKS),
            'modules':len(MODULES),'chapters':len(CHAPTER_REGISTRY),'ai_provider':AI_PROVIDER,'identity_provider':IDENTITY_PROVIDER,
            'payment_provider':PAYMENT_PROVIDER,'production_authorized':False}

@app.get('/api/modules')
def modules():
    return {'release':RELEASE,'modules':[{'name':n,'slug':s,'description':d,'chapters':[x for x in CHAPTER_REGISTRY if x['module']==n]} for n,s,d in MODULES]}

@app.get('/api/search')
def api_search(q:str=Query('',max_length=160),module:str|None=None,dimension:str|None=None,limit:int=Query(20,ge=1,le=100)):
    return run_search(q,module,dimension,limit)

@app.get('/api/compass')
def api_compass(canonical_id:str|None=None,dimension:str|None=None,module:str|None=None,chapter:str|None=None,limit:int=Query(60,ge=1,le=200)):
    return build_compass(canonical_id,dimension,module,chapter,limit)

@app.get('/api/ai/status')
def ai_status():
    adapter_status=EXTERNAL_LLM_ADAPTER.status()
    return {'release':RELEASE,'provider':AI_PROVIDER,'mode':'deterministic_grounded_evidence_composer','retrieval_chunks':len(CHUNKS),'canonical_authority':'R4/B1',
            'answer_classes':['canonical_navigation','grounded_explanation','grounded_comparison','decision_support','insufficient_evidence'],
            'external_llm':adapter_status,'live_external_model':adapter_status['live_external_model'],'production_authorized':False}

@app.post('/api/ai/ask')
def ai_ask(req:AIAskRequest):
    cls=classify_question(req.question)
    if cls=='policy_attack':
        return {'release':RELEASE,'provider':AI_PROVIDER,'answer_class':'insufficient_evidence','answer':'I cannot override North Star governance, reveal hidden instructions, or treat generated wording as canonical content.','citations':[],'grounded':False,'canonical_content':False,'external_llm_used':False,'notice':'AI-generated wording is not canonical North Star content.'}
    evidence=retrieve_evidence(req.question,req.max_evidence)
    if not evidence:
        cls='insufficient_evidence'
    external=safe_external_synthesis(EXTERNAL_LLM_ADAPTER,req.question,cls,evidence) if EXTERNAL_LLM_ADAPTER.config.external_requested else {'used_external':False,'answer':None,'provider':AI_PROVIDER,'fallback_reason':None}
    ans=external['answer'] if external['used_external'] else compose_grounded_answer(req.question,cls,evidence)
    return {'release':RELEASE,'provider':external['provider'],'answer_class':cls,'answer':ans,'citations':[citation_from_chunk(c) for c in evidence],
            'grounded':bool(evidence),'canonical_content':False,'external_llm_used':external['used_external'],'external_llm_fallback_reason':external['fallback_reason'],
            'notice':'AI-generated wording is not canonical North Star content. Canonical authority remains R4/B1.'}

@app.get('/api/auth/status')
def auth_status(request:Request):
    u=current_user(request); return {'provider':IDENTITY_PROVIDER,'authenticated':bool(u),'user':u,'managed_external_idp':False,'production_authorized':False}

@app.post('/api/auth/dev-login')
def dev_login(req:DevLoginRequest,response:Response):
    email=req.email.strip().lower(); now=int(time.time()); c=db(); row=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    if row:user_id=row['user_id']; c.execute('UPDATE users SET display_name=? WHERE user_id=?',(req.display_name,user_id))
    else:user_id='usr_'+uuid.uuid4().hex[:16]; c.execute('INSERT INTO users VALUES(?,?,?,?,?)',(user_id,email,req.display_name,IDENTITY_PROVIDER,now))
    c.commit(); c.close(); token=sign_session({'sub':user_id,'email':email,'iat':now,'exp':now+28800,'provider':IDENTITY_PROVIDER})
    response.set_cookie(SESSION_COOKIE,token,httponly=True,samesite='lax',secure=False,max_age=28800); audit('identity.dev_login',{'provider':IDENTITY_PROVIDER},user_id)
    return {'authenticated':True,'user_id':user_id,'provider':IDENTITY_PROVIDER,'notice':'DEV identity simulator only; no managed external IdP claim.'}

@app.post('/api/auth/logout')
def logout(response:Response):
    response.delete_cookie(SESSION_COOKIE); return {'authenticated':False}

@app.get('/api/entitlements/me')
def my_entitlements(request:Request):
    u=require_user(request); return {'user_id':u['user_id'],'authority':'SERVER_SIDE_ENTITLEMENT_DB','effective':effective_entitlements(u['user_id']),'production_authorized':False}

@app.get('/api/commerce/plans')
def commerce_plans():return {'provider_first':'PayPal','provider_runtime':PAYMENT_PROVIDER,'plans':PLANS,'currency':'USD','production_authorized':False}

@app.get('/api/commerce/paypal/status')
def paypal_status():return {'provider':'PayPal','runtime':PAYMENT_PROVIDER,'sandbox_connected':False,'live_connected':False,'webhook_verified':False,'notice':'DEV simulator. No external PayPal transaction is claimed.'}

@app.post('/api/commerce/paypal/create-order')
def create_order(req:CreateOrderRequest,request:Request):
    u=require_user(request)
    if req.plan_code not in PLANS or req.plan_code=='preview':raise HTTPException(400,'invalid_paid_plan')
    c=db(); existing=c.execute('SELECT * FROM orders WHERE idempotency_key=?',(req.idempotency_key,)).fetchone()
    if existing:
        c.close(); return {'idempotent':True,'order':dict(existing),'provider_runtime':PAYMENT_PROVIDER}
    p=PLANS[req.plan_code]; oid='NSO-'+uuid.uuid4().hex[:14].upper(); poid='PAYPAL-DEV-'+uuid.uuid4().hex[:16].upper(); now=int(time.time())
    c.execute('INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?)',(oid,u['user_id'],PAYMENT_PROVIDER,poid,req.plan_code,p['price'],p['currency'],'CREATED',req.idempotency_key,now,None)); c.commit(); c.close()
    audit('commerce.order_created',{'provider_order_id':poid,'plan':req.plan_code},u['user_id'])
    return {'idempotent':False,'provider':'PayPal','provider_runtime':PAYMENT_PROVIDER,'provider_order_id':poid,'status':'CREATED','plan':req.plan_code,'amount':p['price'],'currency':p['currency'],'notice':'DEV simulation only; no external PayPal transaction occurred.'}

@app.post('/api/commerce/paypal/dev-capture')
def capture_order(req:CaptureOrderRequest,request:Request):
    u=require_user(request); c=db(); row=c.execute('SELECT * FROM orders WHERE provider_order_id=?',(req.provider_order_id,)).fetchone()
    if not row:c.close(); raise HTTPException(404,'order_not_found')
    if row['user_id']!=u['user_id']:c.close(); raise HTTPException(403,'order_owner_mismatch')
    if row['status']=='COMPLETED':
        c.close(); return {'idempotent':True,'provider_order_id':req.provider_order_id,'status':'COMPLETED','effective_entitlements':effective_entitlements(u['user_id'])}
    now=int(time.time()); c.execute("UPDATE orders SET status='COMPLETED',captured_at=? WHERE provider_order_id=?",(now,req.provider_order_id)); c.commit(); plan=row['plan_code']; c.close()
    grant_entitlement(u['user_id'],plan,req.provider_order_id); audit('commerce.payment_completed',{'provider_order_id':req.provider_order_id,'plan':plan},u['user_id'])
    return {'idempotent':False,'provider':'PayPal','provider_runtime':PAYMENT_PROVIDER,'provider_order_id':req.provider_order_id,'status':'COMPLETED','effective_entitlements':effective_entitlements(u['user_id']),'notice':'DEV capture simulation; entitlement granted from server-side completed state.'}

@app.get('/api/commerce/orders')
def order_history(request:Request):
    u=require_user(request); c=db(); rows=c.execute('SELECT order_id,provider,provider_order_id,plan_code,amount,currency,status,created_at,captured_at FROM orders WHERE user_id=? ORDER BY created_at DESC',(u['user_id'],)).fetchall(); c.close(); return {'orders':[dict(r) for r in rows]}

@app.get('/api/audit/me')
def audit_me(request:Request):
    u=require_user(request); c=db(); rows=c.execute('SELECT event_id,event_type,detail,created_at FROM audit_events WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(u['user_id'],)).fetchall(); c.close(); return {'events':[dict(r) for r in rows]}

@app.get('/api/chapters/{module_slug}/{chapter_code}')
def api_chapter(module_slug:str,chapter_code:str):
    module=MODULE_BY_SLUG.get(module_slug.lower())
    if not module: raise HTTPException(404,'module_not_found')
    code=chapter_code.upper()
    meta=next((x for x in CHAPTER_REGISTRY if x['module']==module and x['chapter_code']==code),None)
    if not meta: raise HTTPException(404,'chapter_not_found')
    items=CHAPTER_CONTENT.get((module,code),[])
    return {'release':RELEASE,'module':module,'chapter':meta,'knowledge_blocks':items,'count':len(items)}

def run_search(q,module=None,dimension=None,limit=20):
    q=(q or '').strip().lower(); terms=[t for t in re.findall(r'[a-z0-9]+',q) if len(t)>1]
    dim=(dimension or '').strip().upper()
    if dim and dim not in DIMENSIONS: raise HTTPException(400,'unknown_dimension')
    scored=[]
    for r in SEARCH:
        if module and (r.get('module') or '').lower()!=module.lower(): continue
        if dim and dim not in (r.get('dimension_tags') or []): continue
        hay=' '.join(str(r.get(k,'')) for k in ['title','text','module','chapter']).lower()
        if terms and not all(t in hay for t in terms): continue
        score=sum(hay.count(t) for t in terms) if terms else 1
        scored.append((score,r))
    scored.sort(key=lambda x:(-x[0],x[1].get('canonical_id','')))
    out=[]
    for score,r in scored[:limit]:
        item=dict(r); item['score']=score; item['reader_route']=normalize_route(r); item['compass_route']=f"/compass?canonical_id={quote_plus(r.get('canonical_id',''))}"; out.append(item)
    return {'release':RELEASE,'query':q,'filters':{'module':module,'dimension':dim or None},'count':len(scored),'results':out,'facets':{'dimensions':dimension_counts()}}

def normalize_route(r):
    cid=r.get('canonical_id','')
    if cid.startswith('NS-E-'):
        m=re.match(r'NS-E-(E\d+)-S(\d+)',cid)
        if m: return f'/modules/executive/chapters/{m.group(1).lower()}#kb-{int(m.group(2)):03d}'
    route=r.get('route') or r.get('deep_link') or ''
    if route.startswith('/modules/'): return route
    chapter=chapter_from_record(r)
    return chapter_route(r.get('module'),chapter)+(f"#{cid}" if cid else '')

CSS='''
:root{--navy:#071b2b;--navy2:#0d2a3d;--gold:#c7a45a;--ink:#14202a;--muted:#657784;--paper:#f7f4ed;--line:#d8d4c9;--white:#fff}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink);background:#fbfaf6;line-height:1.55}a{color:#8b651c}.skip{position:absolute;left:-999px}.skip:focus{left:12px;top:12px;background:#fff;padding:10px;z-index:99}.top{background:var(--navy);color:#fff;position:sticky;top:0;z-index:20;border-bottom:1px solid #294255}.top .shell{height:66px;display:flex;align-items:center;justify-content:space-between}.brand{font-family:Georgia,serif;letter-spacing:.18em;font-weight:700;color:#fff;text-decoration:none}.brand span{color:var(--gold)}nav a{color:#d9e2e8;text-decoration:none;margin-left:22px;font-size:.92rem}.shell{max-width:1180px;margin:auto;padding:0 28px}.hero{background:radial-gradient(circle at 80% 15%,#173f59 0,transparent 28%),linear-gradient(145deg,var(--navy),#0a2538);color:#fff;padding:78px 0 72px}.eyebrow{text-transform:uppercase;letter-spacing:.18em;color:var(--gold);font-size:.75rem;font-weight:700}.hero h1{font-family:Georgia,serif;font-size:clamp(2.6rem,6vw,5.5rem);line-height:.95;margin:.18em 0}.hero p{max-width:720px;color:#c4d2dc;font-size:1.15rem}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:28px}.btn{display:inline-block;padding:11px 17px;border-radius:4px;background:var(--gold);color:#071b2b;text-decoration:none;font-weight:700}.btn.secondary{background:transparent;color:#fff;border:1px solid #6b8190}.section{padding:58px 0}.section h2{font-family:Georgia,serif;font-size:2rem;margin:.2em 0}.lede{color:var(--muted);max-width:780px}.journey{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:28px}.card{background:#fff;border:1px solid var(--line);padding:22px;border-radius:6px;box-shadow:0 8px 28px #1020300a}.card .num{color:var(--gold);font-family:Georgia,serif;font-size:1.7rem}.card h3{margin:.25em 0;font-family:Georgia,serif}.card a{text-decoration:none;font-weight:700}.searchbox{background:#fff;border:1px solid var(--line);padding:18px;border-radius:6px;display:grid;grid-template-columns:1fr 170px 170px auto;gap:10px}.searchbox input,.searchbox select{width:100%;padding:12px;border:1px solid #c8c3b8;border-radius:4px;background:#fff}.searchbox button{border:0;border-radius:4px;background:var(--navy);color:#fff;padding:0 18px;font-weight:700}.results{margin-top:18px}.result{background:#fff;border-bottom:1px solid var(--line);padding:18px}.meta{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.result h3{margin:.3em 0}.result h3 a{text-decoration:none}.result p{margin:.25em 0;color:#40515c}.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.tag{font-size:.72rem;border:1px solid #d5c79e;padding:3px 7px;border-radius:20px;color:#76581f}.module-hero{background:var(--navy);color:#fff;padding:42px 0}.module-grid{display:grid;grid-template-columns:280px 1fr;gap:32px}.chapter-nav{position:sticky;top:90px;align-self:start;background:#fff;border:1px solid var(--line);padding:16px}.chapter-nav a{display:block;padding:7px 5px;text-decoration:none;border-bottom:1px solid #eee}.reader{background:#fff;border:1px solid var(--line);padding:clamp(24px,5vw,58px);max-width:820px}.reader h1,.reader h2{font-family:Georgia,serif}.kb{padding:22px 0;border-top:1px solid #e6e1d7;scroll-margin-top:88px}.kb:first-of-type{border-top:0}.kb-id{font-size:.7rem;letter-spacing:.08em;color:#82909a}.reader-tools{display:flex;gap:8px;margin-bottom:24px}.reader-tools button{padding:7px 10px;border:1px solid #bbb;background:#fff;border-radius:4px}.focus .chapter-nav,.focus .top{display:none}.focus .module-grid{grid-template-columns:1fr}.focus .reader{margin:auto}.footer{background:#061622;color:#9fb0bb;padding:32px 0;margin-top:50px}.compass-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:24px 0}.dimension-card{background:#fff;border:1px solid var(--line);padding:13px;text-decoration:none;color:var(--ink);border-radius:5px}.dimension-card.active{border:2px solid var(--gold);background:#fffaf0}.dimension-card b{display:block;font-size:.75rem}.dimension-card span{font-size:.72rem;color:var(--muted)}.compass-layout{display:grid;grid-template-columns:300px 1fr;gap:28px}.compass-panel{background:var(--navy);color:#fff;padding:22px;border-radius:6px;align-self:start}.compass-list{background:#fff;border:1px solid var(--line)}.compass-item{padding:15px;border-bottom:1px solid #eee}.compass-item a{text-decoration:none;font-weight:700}.rel{font-size:.75rem;color:var(--muted);margin-top:5px}.empty{padding:28px;color:var(--muted)}.ai-shell{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:28px}.ai-panel{background:#fff;border:1px solid var(--line);padding:22px;border-radius:6px}.ai-panel textarea{width:100%;min-height:120px;padding:12px;border:1px solid #c8c3b8;border-radius:4px;font:inherit}.ai-answer{white-space:pre-wrap;background:#fffaf0;border-left:4px solid var(--gold);padding:18px;margin-top:18px}.citation{border-top:1px solid #eee;padding:10px 0;font-size:.86rem}.notice{font-size:.78rem;color:#657784}.account-grid{display:grid;grid-template-columns:340px 1fr;gap:28px}.account-panel{background:#fff;border:1px solid var(--line);padding:22px;border-radius:6px}.account-panel input{width:100%;padding:11px;border:1px solid #c8c3b8;border-radius:4px;margin:6px 0 12px}.plans{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.plan{border:1px solid var(--line);padding:16px;border-radius:5px}.plan .price{font-family:Georgia,serif;font-size:1.7rem}.status-pill{display:inline-block;padding:4px 9px;border-radius:20px;background:#e9f2ea;color:#285b31;font-size:.75rem;font-weight:700}.warning-pill{background:#fff1d9;color:#7a5511}
@media(max-width:900px){.journey{grid-template-columns:repeat(2,1fr)}.searchbox{grid-template-columns:1fr 1fr}.searchbox input{grid-column:1/-1}.module-grid,.compass-layout,.ai-shell,.account-grid{grid-template-columns:1fr}.chapter-nav{position:relative;top:auto}.compass-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:560px){.shell{padding:0 17px}.top .shell{height:auto;min-height:62px;align-items:flex-start;padding-top:14px;padding-bottom:12px}.top nav{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}.top nav a{margin-left:0;font-size:.78rem}.journey{grid-template-columns:1fr}.searchbox{grid-template-columns:1fr}.searchbox input{grid-column:auto}.compass-grid{grid-template-columns:repeat(2,1fr)}.plans{grid-template-columns:1fr}.hero{padding:55px 0}.section{padding:38px 0}.reader{padding:22px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{animation:none!important;transition:none!important}}
'''

def layout(title,body):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} | North Star</title><style>{CSS}</style></head><body><a class="skip" href="#main">Skip to content</a><header class="top"><div class="shell"><a class="brand" href="/">NORTH <span>STAR</span></a><nav aria-label="Primary"><a href="/">Portal</a><a href="/search">Search</a><a href="/compass">Compass</a><a href="/assistant">Ask North Star</a><a href="/account">Account</a></nav></div></header>{body}<footer class="footer"><div class="shell">North Star · Governed R4/B1 digital experience · {RELEASE} · DEV runtime</div></footer></body></html>'''

@app.get('/',response_class=HTMLResponse)
def home():
    cards=''.join([f'<article class="card"><div class="num">0{i}</div><h3>{n}</h3><p>{escape(d)}</p><a href="/modules/{s}">Explore {n} →</a></article>' for i,(n,s,d) in enumerate(MODULES,1)])
    body=f'''<main id="main"><section class="hero"><div class="shell"><div class="eyebrow">The Executive Guide to Enterprise Technology, Leadership & Transformation</div><h1>Find direction.<br>Lead with purpose.</h1><p>One governed North Star. Four levels. Eleven dimensions. Move from understanding to executive judgment without losing the source.</p><div class="actions"><a class="btn" href="/modules/foundation">Start the journey</a><a class="btn secondary" href="/search">Search North Star</a><a class="btn secondary" href="/compass">Open Compass</a></div></div></section><section class="section"><div class="shell"><div class="eyebrow">Progression</div><h2>Foundation → Professional → Executive → Leadership</h2><p class="lede">Each level builds a different capability while remaining anchored to the same governed R4 publication baseline.</p><div class="journey">{cards}</div></div></section><section class="section" style="background:#f1eee6"><div class="shell"><div class="eyebrow">Reader model</div><h2>Understand → Decide → Do</h2><p class="lede">North Star is designed to move knowledge into judgment and judgment into disciplined action.</p></div></section></main>'''
    return layout('Portal',body)

@app.get('/search',response_class=HTMLResponse)
def search_page(q:str='',module:str='',dimension:str=''):
    data=run_search(q,module or None,dimension or None,50) if (q or module or dimension) else {'results':[],'count':0}
    module_opts='<option value="">All modules</option>'+''.join([f'<option {"selected" if module==n else ""}>{n}</option>' for n,_,_ in MODULES])
    dim_opts='<option value="">All dimensions</option>'+''.join([f'<option {"selected" if dimension.upper()==d else ""}>{d}</option>' for d in DIMENSIONS])
    results=''.join([f'''<article class="result"><div class="meta">{escape(r.get('module',''))} · {escape(chapter_from_record(r) or '')} · {escape(r.get('canonical_id',''))}</div><h3><a href="{escape(r['reader_route'])}">{escape(r.get('title') or r.get('canonical_id',''))}</a></h3><p>{escape((r.get('text') or '')[:300])}</p><div class="tags">{''.join(f'<a class="tag" href="/compass?dimension={escape(d)}">{escape(d)}</a>' for d in r.get('dimension_tags',[]) or [])}<a class="tag" href="{escape(r['compass_route'])}">Open in Compass</a></div></article>''' for r in data['results']])
    if (q or module or dimension) and not results: results='<div class="empty">No governed North Star content matched this search.</div>'
    body=f'''<main id="main"><section class="module-hero"><div class="shell"><div class="eyebrow">Governed discovery</div><h1 style="font-family:Georgia,serif;margin:.2em 0">Search North Star</h1><p style="color:#c4d2dc">Search the governed R4/B1 corpus and move directly into the canonical reader or Compass context.</p></div></section><section class="section"><div class="shell"><form class="searchbox" method="get"><input aria-label="Search query" name="q" value="{escape(q)}" placeholder="Search strategy, governance, architecture, resilience…"><select aria-label="Module" name="module">{module_opts}</select><select aria-label="Dimension" name="dimension">{dim_opts}</select><button>Search</button></form><div class="results" aria-live="polite"><p class="meta">{data['count']} governed matches</p>{results}</div></div></section></main>'''
    return layout('Search',body)

@app.get('/compass',response_class=HTMLResponse)
def compass_page(canonical_id:str|None=None,dimension:str|None=None,module:str|None=None,chapter:str|None=None):
    data=build_compass(canonical_id,dimension,module,chapter,80); ctx=data['filters']; counts=data['dimension_counts']; selected=ctx.get('dimension') or 'ALL DIMENSIONS'
    cards=''.join([f'<a class="dimension-card {"active" if selected==d else ""}" href="/compass?dimension={d}"><b>{d}</b><span>{counts[d]} governed records</span></a>' for d in DIMENSIONS])
    content=[n for n in data['nodes'] if n['type']=='content']
    items=''.join([f'<article class="compass-item"><div class="meta">{escape(n["meta"].get("module","") or "")} · {escape(n["meta"].get("chapter","") or "")} · {escape(n["id"])}</div><a href="{escape(n.get("route") or "#")}">{escape(n["label"] or n["id"])}</a><div class="rel">Governed dimensions: {escape(", ".join(n["meta"].get("dimensions",[])) or "none")}</div></article>' for n in content]) or '<div class="empty">No governed relationships matched the selected context. No relationship has been inferred.</div>'
    body=f'''<main id="main"><section class="module-hero"><div class="shell"><div class="eyebrow">North Star Compass™</div><h1 style="font-family:Georgia,serif;margin:.2em 0">Orient by relationship, not by menu</h1><p style="color:#c4d2dc;max-width:780px">Traverse the governed R4/B1 corpus through the 11 Executive Leadership Dimensions. Compass never invents a canonical relationship.</p></div></section><section class="section"><div class="shell"><h2>11 Dimensions</h2><p class="lede">Each connection below is derived from governed B1 dimension tags, hierarchy or approved chapter sequence.</p><div class="compass-grid">{cards}</div><div class="compass-layout"><aside class="compass-panel"><div class="eyebrow">Current orientation</div><h2>{escape(selected)}</h2><p>{escape(DIMENSION_DESCRIPTIONS.get(ctx.get('dimension'),'Select a dimension or open a result from Search to see its governed neighborhood.'))}</p><p><b>{data['result_count']}</b> content objects in the current bounded view.</p><p style="font-size:.85rem;color:#657784">Source: {escape(data['source_release_identity'])}<br>Edges: governed metadata/hierarchy only.</p></aside><section><h2>Governed content relationships</h2><div class="compass-list">{items}</div></section></div></div></section></main>'''
    return layout('Compass',body)

@app.get('/assistant',response_class=HTMLResponse)
def assistant_page():
    body='''<main id="main"><section class="module-hero"><div class="shell"><div class="eyebrow">Grounded AI</div><h1 style="font-family:Georgia,serif;margin:.2em 0">Ask North Star</h1><p style="color:#c4d2dc;max-width:780px">Ask for explanation, comparison, navigation or decision support. Answers are generated only from governed R4/B1 retrieval evidence and cite their sources.</p></div></section><section class="section"><div class="shell ai-shell"><section class="ai-panel"><label for="q"><b>Your question</b></label><textarea id="q" placeholder="Example: How should an executive think about governance and risk?"></textarea><div class="actions"><button class="btn" id="ask" type="button">Ask North Star</button></div><div id="answer" aria-live="polite"></div></section><aside class="ai-panel"><div class="eyebrow">AI governance</div><h2>Grounded, not canonical</h2><p>This assistant may explain, navigate, compare and support decisions. It may not silently rewrite North Star or present generated wording as canonical R4 content.</p><p class="notice">Provider execution is runtime-controlled. Responses remain grounded in governed R4/B1 evidence; generated wording is not canonical North Star content.</p></aside></div></section></main><script>
document.getElementById('ask').addEventListener('click',async function(){
    const button=this,q=document.getElementById('q').value.trim(),a=document.getElementById('answer');
    if(!q){a.textContent='Enter a North Star question first.';return;}
    button.disabled=true;a.innerHTML='<p>Retrieving governed evidence…</p>';
    try{
        const r=await fetch('/api/ai/ask',{method:'POST',credentials:'same-origin',headers:{'content-type':'application/json'},body:JSON.stringify({question:q,max_evidence:6})});
        let d;
        try{d=await r.json();}catch(e){throw new Error('invalid_response');}
        if(!r.ok)throw new Error(d.detail||('request_failed_'+r.status));
        const c=(d.citations||[]).map(x=>`<div class="citation"><b>${x.canonical_id||x.chunk_id}</b> · ${x.module||''} ${x.chapter||''}<br><a href="${x.route||'#'}">Open governed source</a></div>`).join('');
        const answer=String(d.answer||'').split(String.fromCharCode(10)).join('<br>');
        a.innerHTML=`<div class="ai-answer"><div class="meta">${d.answer_class||''} · ${d.provider||''}</div>${answer}</div><h3>Governed evidence</h3>${c}<p class="notice">${d.notice||''}</p>`;
    }catch(e){
        a.innerHTML='<div class="empty">Ask North Star could not complete this request. No answer has been accepted. Please retry only after the service status is verified.</div>';
    }finally{button.disabled=false;}
});
</script>'''
    return layout('Ask North Star',body)

@app.get('/account',response_class=HTMLResponse)
def account_page():
    plan_cards=''.join([f'''<article class="plan"><div class="eyebrow">{escape(code)}</div><h3>{escape(p['name'])}</h3><div class="price">${escape(p['price'])}</div><p>{escape(p['description'])}</p>{'' if code=='preview' else f'<button class="btn buy" data-plan="{code}">Create DEV PayPal order</button>'}</article>''' for code,p in PLANS.items()])
    body='''<main id="main"><section class="module-hero"><div class="shell"><div class="eyebrow">Identity · Commerce · Access</div><h1 style="font-family:Georgia,serif;margin:.2em 0">North Star Account</h1><p style="color:#c4d2dc">Authentication proves identity. Entitlement authorizes access. Only server-verified commercial evidence establishes paid state.</p></div></section><section class="section"><div class="shell account-grid"><aside class="account-panel"><div class="eyebrow">DEV identity</div><h2>Sign in</h2><label>Email<input id="email" type="email" value="reader@example.com"></label><label>Display name<input id="name" value="North Star Reader"></label><button class="btn" id="login">DEV sign in</button><div id="auth" aria-live="polite" style="margin-top:15px"></div><hr><h3>Effective entitlement</h3><div id="ent">Sign in to inspect server-side entitlement.</div></aside><section><div class="eyebrow">PayPal-first commercial model</div><h2>Plans</h2><p class="notice">This runtime uses PAYPAL_SIMULATOR. No external PayPal transaction, credential, webhook or settlement is claimed.</p><div class="plans">{plan_cards}</div><div id="order" aria-live="polite" style="margin-top:18px"></div></section></div></section></main><script>
async function refresh(){let a=await fetch('/api/auth/status').then(r=>r.json());document.getElementById('auth').innerHTML=a.authenticated?`<span class="status-pill">Signed in</span><p>${a.user.email}</p>`:'<span class="status-pill warning-pill">Not signed in</span>';if(a.authenticated){let e=await fetch('/api/entitlements/me').then(r=>r.json());document.getElementById('ent').innerHTML=`<pre>${JSON.stringify(e.effective,null,2)}</pre>`}}
document.getElementById('login').onclick=async()=>{await fetch('/api/auth/dev-login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email:document.getElementById('email').value,display_name:document.getElementById('name').value})});refresh()};
document.querySelectorAll('.buy').forEach(b=>b.onclick=async()=>{let k='ui-'+crypto.randomUUID(),r=await fetch('/api/commerce/paypal/create-order',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({plan_code:b.dataset.plan,idempotency_key:k})});let d=await r.json();if(!r.ok){document.getElementById('order').textContent=d.detail||'Sign in first';return}document.getElementById('order').innerHTML=`<div class="ai-answer"><b>DEV order created</b><br>${d.provider_order_id}<br><button class="btn" id="capture">Simulate completed PayPal capture</button></div>`;document.getElementById('capture').onclick=async()=>{let c=await fetch('/api/commerce/paypal/dev-capture',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({provider_order_id:d.provider_order_id})}).then(x=>x.json());document.getElementById('order').innerHTML=`<div class="ai-answer"><b>${c.status}</b><br>Server-side entitlement updated.</div>`;refresh()}});refresh();</script>'''.replace('{plan_cards}',plan_cards)
    return layout('Account',body)

@app.get('/modules/{module_slug}',response_class=HTMLResponse)
def module_page(module_slug:str):
    module=MODULE_BY_SLUG.get(module_slug.lower())
    if not module: raise HTTPException(404)
    desc=next(d for n,s,d in MODULES if s==module_slug.lower())
    chapters=[x for x in CHAPTER_REGISTRY if x['module']==module]
    cards=''.join([f'<article class="card"><div class="meta">{escape(c["chapter_code"])}</div><h3>{escape(c["chapter_title"])}</h3><a href="/modules/{module_slug}/chapters/{c["chapter_code"].lower()}">Read chapter →</a></article>' for c in chapters])
    body=f'''<main id="main"><section class="module-hero"><div class="shell"><div class="eyebrow">North Star {escape(module)}</div><h1 style="font-family:Georgia,serif;font-size:3rem;margin:.15em 0">{escape(module)}</h1><p style="color:#c4d2dc;max-width:760px">{escape(desc)}</p></div></section><section class="section"><div class="shell"><div class="journey" style="grid-template-columns:repeat(3,1fr)">{cards}</div></div></section></main>'''
    return layout(module,body)

@app.get('/modules/{module_slug}/chapters/{chapter_code}',response_class=HTMLResponse)
def chapter_page(module_slug:str,chapter_code:str):
    module=MODULE_BY_SLUG.get(module_slug.lower())
    if not module: raise HTTPException(404)
    code=chapter_code.upper(); chapters=[x for x in CHAPTER_REGISTRY if x['module']==module]
    meta=next((x for x in chapters if x['chapter_code']==code),None)
    if not meta: raise HTTPException(404)
    nav=''.join([f'<a href="/modules/{module_slug}/chapters/{c["chapter_code"].lower()}"><b>{escape(c["chapter_code"])}</b> {escape(c["chapter_title"])}</a>' for c in chapters])
    items=CHAPTER_CONTENT.get((module,code),[])
    blocks=''.join([f'''<section class="kb" id="kb-{i:03d}"><div class="kb-id">{escape(r.get('canonical_id',''))}</div>{f'<h2>{escape(r.get("title"))}</h2>' if r.get('title') else ''}<div>{escape(r.get('text','')).replace(chr(10),'<br>')}</div><div class="tags">{''.join(f'<a class="tag" href="/compass?dimension={escape(d)}">{escape(d)}</a>' for d in r.get('dimension_tags',[]) or [])}</div></section>''' for i,r in enumerate(items,1)])
    if not blocks: blocks='<p>No governed content blocks were mapped for this chapter.</p>'
    body=f'''<main id="main"><section class="module-hero"><div class="shell"><div class="eyebrow">{escape(module)} · {escape(code)}</div><h1 style="font-family:Georgia,serif;margin:.2em 0">{escape(meta['chapter_title'])}</h1><p><a style="color:#e0c47d" href="/compass?module={quote_plus(module)}&chapter={quote_plus(code)}">Open chapter in Compass →</a></p></div></section><section class="section"><div class="shell module-grid"><aside class="chapter-nav" aria-label="Chapter navigation"><b>{escape(module)} chapters</b>{nav}</aside><article class="reader" id="reader"><div class="reader-tools" aria-label="Reader controls"><button onclick="size(1)" aria-label="Increase text size">A+</button><button onclick="size(-1)" aria-label="Decrease text size">A−</button><button onclick="document.body.classList.toggle('focus')">Focus mode</button></div><div class="eyebrow">Understand → Decide → Do</div><h1>{escape(meta['chapter_title'])}</h1><p class="lede">Canonical digital reading view · {len(items)} governed knowledge blocks</p>{blocks}</article></div></section></main><script>let fs=Number(localStorage.nsFont||100);function size(d){{fs=Math.max(85,Math.min(135,fs+d*10));document.getElementById('reader').style.fontSize=fs+'%';localStorage.nsFont=fs}}document.getElementById('reader').style.fontSize=fs+'%';localStorage.setItem('nsProgress:{module}:{code}','opened')</script>'''
    return layout(meta['chapter_title'],body)
