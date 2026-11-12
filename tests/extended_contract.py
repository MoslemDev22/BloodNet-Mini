"""Additional black-box checks for BloodNet's participant API.
Run after starting service/bloodnet_api.py. Does not modify the official harness.
"""
import json, sys, uuid, urllib.request, urllib.error
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
passed = 0; failed = 0

def call(method, path, body=None, token=None, key=None):
    headers = {"Content-Type": "application/json"}
    if token: headers["Authorization"] = "Bearer " + token
    if key: headers["Idempotency-Key"] = key
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read(); return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read(); return e.code, json.loads(raw) if raw else {}

def check(name, condition, detail=""):
    global passed, failed
    if condition: passed += 1; print("PASS", name, detail)
    else: failed += 1; print("FAIL", name, detail)

c, j = call("GET", "/health"); check("health", c == 200 and j.get("ok") is True, str(c))
c, _ = call("POST", "/requests", {"hospital_id":"H01","blood_group":"O+","product":"red_cells","units":1,"urgency":"urgent"})
check("hospital auth required", c == 401, str(c))
key = "ext-" + uuid.uuid4().hex
body = {"hospital_id":"H01","blood_group":"O+","product":"red_cells","units":1,"urgency":"urgent"}
c1, j1 = call("POST", "/requests", body, "hospital-token", key)
c2, j2 = call("POST", "/requests", body, "hospital-token", key)
check("create request", c1 == 201 and bool(j1.get("request_id")), str(c1))
check("idempotent replay", c2 == 200 and j1.get("request_id") == j2.get("request_id"), str(c2))
c3, _ = call("POST", "/requests", {**body,"units":2}, "hospital-token", key)
check("idempotency body conflict", c3 == 422, str(c3))
c4, _ = call("POST", "/requests", {**body,"unexpected":True}, "hospital-token", "extra-"+uuid.uuid4().hex)
check("reject unknown fields", c4 == 400, str(c4))
c5, _ = call("POST", "/requests", {**body,"hospital_id":"H98"}, "hospital-token", "fake-"+uuid.uuid4().hex)
check("reject unregistered hospital", c5 == 404, str(c5))
rid = j1.get("request_id")
c6, j6 = call("GET", "/requests/"+rid, token="hospital-token")
check("request state endpoint", c6 == 200 and all(k in j6 for k in ("needed","confirmed","en_route","arrived","fulfilled")), str(c6))
c7, _ = call("POST", "/requests/"+rid+"/amend", {"urgency":"critical"}, "hospital-token")
check("amend urgency", c7 == 200, str(c7))
c8, _ = call("POST", "/requests/"+rid+"/cancel", {}, "hospital-token")
c9, _ = call("POST", "/requests/"+rid+"/cancel", {}, "hospital-token")
check("idempotent cancellation", c8 == 200 and c9 == 200, f"{c8}/{c9}")
# Abuse policy: extreme critical demand is held for coordinator review and not mobilized.
k2 = "abuse-" + uuid.uuid4().hex
c10, j10 = call("POST", "/requests", {"hospital_id":"H09","blood_group":"O-","product":"red_cells","units":8,"urgency":"critical"}, "hospital-token", k2)
check("abuse request held", c10 == 201 and j10.get("status") == "pending_review", str(j10.get("status")))
if j10.get("request_id"):
    c11, _ = call("POST", "/requests/"+j10["request_id"]+"/approve", {}, "coordinator-token")
    check("coordinator approval", c11 == 200, str(c11))
else: check("coordinator approval", False, "request was not created")
# Callback idempotency, including a repeated event_id.
ev = {"event_id":"ext-event-"+uuid.uuid4().hex,"request_id":rid,"donor_id":"D00001","event":"en_route","sim_time":12.5}
c12, _ = call("POST", "/callbacks/donor-progress", ev)
c13, j13 = call("POST", "/callbacks/donor-progress", ev)
check("callback duplicate accepted once", c12 == 200 and c13 == 200 and j13.get("duplicate") is True, f"{c12}/{c13}")
c14, _ = call("POST", "/callbacks/donor-response", {"event_id":"bad","request_id":rid,"donor_id":"D00001","response":"maybe","notification_id":"x","sim_time":1})
check("callback enum validation", c14 == 400, str(c14))
c15, _ = call("GET", "/requests", token="hospital-token")
check("request list endpoint", c15 == 200, str(c15))
c16, _ = call("GET", "/donors/D00001/invitations", token="wrong-token")
check("donor portal protected", c16 == 401, str(c16))
print(f"\n{passed}/{passed+failed} checks passed")
sys.exit(0 if failed == 0 else 1)
