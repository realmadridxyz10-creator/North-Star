import json, math, statistics, time
from urllib import request, error

BASE='https://north-star-uat-r4-production.up.railway.app'
ITERATIONS=75
WARMUPS=5
TIMEOUT=20

# Provisional UAT objectives for the current deterministic runtime.
# These are not yet production SLOs; they are release-evidence thresholds.
THRESHOLDS_MS={
    'Search': {'p95':1000.0,'p99':1500.0},
    'Compass': {'p95':1000.0,'p99':1500.0},
    'Grounded AI (LOCAL_EVIDENCE)': {'p95':1500.0,'p99':2500.0},
}

def pct(vals,p):
    if not vals: return float('nan')
    s=sorted(vals)
    k=(len(s)-1)*(p/100.0)
    f=math.floor(k); c=math.ceil(k)
    if f==c: return s[int(k)]
    return s[f]*(c-k)+s[c]*(k-f)

def call(method,path,payload=None):
    data=None if payload is None else json.dumps(payload).encode('utf-8')
    req=request.Request(BASE+path,data=data,method=method)
    if data is not None: req.add_header('Content-Type','application/json')
    t0=time.perf_counter()
    try:
        with request.urlopen(req,timeout=TIMEOUT) as r:
            body=r.read()
            status=r.status
    except error.HTTPError as e:
        status=e.code; body=e.read()
    except Exception as e:
        return None,0.0,str(e)
    ms=(time.perf_counter()-t0)*1000.0
    return status,ms,body.decode('utf-8','replace')

def benchmark(name,method,path,payload=None,validator=None):
    for _ in range(WARMUPS):
        call(method,path,payload)
    lats=[]; failures=[]
    for i in range(ITERATIONS):
        status,ms,body=call(method,path,payload)
        ok=(status==200)
        if ok and validator:
            try: ok=bool(validator(json.loads(body)))
            except Exception: ok=False
        if ok: lats.append(ms)
        else: failures.append({'iteration':i+1,'status':status,'detail':body[:160]})
    success=len(lats); total=ITERATIONS
    res={
        'name':name,'requests':total,'successes':success,'failures':len(failures),
        'success_rate_pct':round(success*100.0/total,2),
        'p50_ms':round(pct(lats,50),2) if lats else None,
        'p95_ms':round(pct(lats,95),2) if lats else None,
        'p99_ms':round(pct(lats,99),2) if lats else None,
        'max_ms':round(max(lats),2) if lats else None,
        'mean_ms':round(statistics.mean(lats),2) if lats else None,
        'failures_sample':failures[:3],
    }
    t=THRESHOLDS_MS[name]
    res['thresholds_ms']=t
    res['pass']=(res['success_rate_pct']==100.0 and res['p95_ms'] is not None and res['p95_ms']<=t['p95'] and res['p99_ms']<=t['p99'])
    print(json.dumps(res,separators=(',',':')))
    return res

results=[]
results.append(benchmark('Search','GET','/api/search?q=governance&limit=20',validator=lambda j:j.get('count',0)>0))
results.append(benchmark('Compass','GET','/api/compass?dimension=BUILD&limit=60',validator=lambda j:len(j.get('nodes',[]))>0 and len(j.get('edges',[]))>0))
results.append(benchmark('Grounded AI (LOCAL_EVIDENCE)','POST','/api/ai/ask',{'question':'How should an executive govern enterprise technology transformation?','max_evidence':6},validator=lambda j:j.get('provider')=='LOCAL_EVIDENCE' and j.get('grounded') is True and len(j.get('citations',[]))>0))

summary={'base':BASE,'iterations_per_endpoint':ITERATIONS,'warmups_per_endpoint':WARMUPS,'results':results,'all_pass':all(r['pass'] for r in results),'note':'External UAT benchmark from GitHub-hosted runner to Railway R4. Thresholds are provisional UAT evidence objectives, not final production SLOs.'}
print('SUMMARY '+json.dumps(summary,separators=(',',':')))
if not summary['all_pass']:
    raise SystemExit(1)
