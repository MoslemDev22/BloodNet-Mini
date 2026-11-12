"""Coordinator review workflow regression tests. Run with the BloodNet API online."""
import json, sys, uuid, urllib.request, urllib.error
BASE=(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000').rstrip('/')
passed=failed=0

def call(method,path,body=None,token=None,key=None):
    h={'Content-Type':'application/json'}
    if token:h['Authorization']='Bearer '+token
    if key:h['Idempotency-Key']=key
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(BASE+path,data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(req,timeout=5) as r:
            raw=r.read();return r.status,json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw=e.read();return e.code,json.loads(raw) if raw else {}

def check(label,ok,detail=''):
    global passed,failed
    passed+=bool(ok);failed+=not bool(ok)
    print(('PASS' if ok else 'FAIL'),label,detail)

# Create a high-risk request guaranteed to enter the manual-review queue.
key='review-'+uuid.uuid4().hex
c,created=call('POST','/requests',{'hospital_id':'H09','blood_group':'B+','product':'platelets','units':20,'urgency':'critical','note':'Coordinator review test'},'hospital-token',key)
rid=created.get('request_id','')
check('20-unit critical request is held',c==201 and created.get('status')=='pending_review',str(created))
if rid:
    c,listing=call('GET','/requests',token='coordinator-token')
    check('coordinator can read request queue',c==200 and any(x.get('request_id')==rid for x in listing.get('items',[])),str(c))
    c,detail=call('GET','/requests/'+rid,token='coordinator-token')
    check('coordinator can read request details',c==200 and detail.get('needed')==20,str(c))
    c,events=call('GET','/requests/'+rid+'/events',token='coordinator-token')
    check('coordinator can read request history',c==200 and bool(events.get('items')),str(c))
    c,_=call('POST','/requests/'+rid+'/approve',{'approved':False,'note':'   '},'coordinator-token')
    check('rejection without reason is blocked',c==400,str(c))
    reason='تعداد ۲۰ واحد نیازمند تأیید مستندات بیمارستان است.'
    c,result=call('POST','/requests/'+rid+'/approve',{'approved':False,'note':reason},'coordinator-token')
    check('coordinator rejection is recorded',c==200 and result.get('status')=='cancelled',str(result))
    c,events=call('GET','/requests/'+rid+'/events',token='coordinator-token')
    rejected=[x for x in events.get('items',[]) if x.get('type')=='review_rejected']
    check('rejection reason is present in event history',bool(rejected) and rejected[-1].get('note')==reason,str(rejected[-1] if rejected else None))
    c,_=call('POST','/requests/'+rid+'/approve',{'approved':True,'note':'late approval'},'coordinator-token')
    check('resolved request cannot be decided twice',c==409,str(c))
# A second pending request validates approval path.
key='approve-'+uuid.uuid4().hex
c,created=call('POST','/requests',{'hospital_id':'H09','blood_group':'AB+','product':'plasma','units':8,'urgency':'critical'},'hospital-token',key)
rid2=created.get('request_id','')
if rid2:
    c,result=call('POST','/requests/'+rid2+'/approve',{'approved':True,'note':'بررسی انجام شد.'},'coordinator-token')
    check('coordinator approval opens request',c==200 and result.get('status')=='open',str(result))
else:check('coordinator approval opens request',False,'request not created')
print(f'\n{passed}/{passed+failed} checks passed')
sys.exit(0 if failed else 1)
