"""BloodNet contest API.

Implements the participant OpenAPI contract and integrates with the local practice
Gateway, Inventory and Travel services. All timestamps and decisions use Gateway
simulation minutes, never wall-clock time. Synthetic contest data only.
"""
from __future__ import annotations
import csv, hashlib, json, os, threading, time, uuid, urllib.parse, urllib.request, urllib.error, sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from typing import Any

try:
    import yaml
except ImportError as exc:  # clear startup error instead of silently using wrong rules
    raise SystemExit("Missing dependency PyYAML. Run: pip install -r requirements-contest.txt") from exc

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path: sys.path.insert(0, BASE)
from harness.simconfig import SNAPSHOT

def load_env(path: str) -> None:
    if not os.path.isfile(path): return
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_env(os.path.join(BASE, ".env"))
PORT = int(os.getenv("PORT", "8000"))
SELF_URL = os.getenv("SELF_URL", f"http://127.0.0.1:{PORT}").rstrip("/")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:9100").rstrip("/")
TRAVEL_URL = os.getenv("TRAVEL_URL", "http://127.0.0.1:9200").rstrip("/")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://127.0.0.1:9300").rstrip("/")
KIT_PATH = os.getenv("KIT_PATH", "participant_kit")
if not os.path.isabs(KIT_PATH): KIT_PATH = os.path.join(BASE, KIT_PATH)
HOSPITAL_TOKEN = os.getenv("HOSPITAL_TOKEN", "hospital-token")
COORDINATOR_TOKEN = os.getenv("COORDINATOR_TOKEN", "coordinator-token")
DONOR_DEMO_TOKEN = os.getenv("DONOR_DEMO_TOKEN", "donor-demo-token")

GROUPS = ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"]
PRODUCTS = ["red_cells", "platelets", "plasma"]
URGENCIES = ["critical", "urgent", "planned"]
EPOCH = SNAPSHOT

# Immutable public kit data. These are the source of truth, not hard-coded approximations.
def read_csv(name: str) -> list[dict[str, str]]:
    with open(os.path.join(KIT_PATH, name), newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

with open(os.path.join(KIT_PATH, "compat.yaml"), encoding="utf-8") as f:
    COMPAT = yaml.safe_load(f)
with open(os.path.join(KIT_PATH, "rules.yaml"), encoding="utf-8") as f:
    RULES = yaml.safe_load(f)
DONORS = read_csv("donors.csv")
DONOR_BY_ID = {d["donor_id"]: d for d in DONORS}
HISTORY_STATS: dict[str, dict[str, int]] = {}
try:
    for row in read_csv("history/responses.csv"):
        did = row["donor_id"]
        st = HISTORY_STATS.setdefault(did, {"responded": 0, "accepted": 0, "arrived": 0, "donated": 0})
        for key in st: st[key] += int(row.get(key, "0") or 0)
except OSError:
    pass
HOSPITAL_ROWS = read_csv("hospitals.csv")
HOSPITAL_BY_ID = {h["hospital_id"]: h for h in HOSPITAL_ROWS}
CENTERS = {c["center_id"]: c for c in read_csv("centers.csv")}
TRAVEL_MIN: dict[tuple[str, str], float] = {}
with open(os.path.join(KIT_PATH, "travel_area_to_hospital.csv"), newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        for hid in HOSPITAL_BY_ID:
            try: TRAVEL_MIN[(row["area_id"], hid)] = float(row[hid])
            except (KeyError, ValueError): pass
# The latest donor event supersedes older events for that donor.
DEFER_UNTIL: dict[str, datetime] = {}
_DEFER_EVENT_AT: dict[str, datetime] = {}
for ev in read_csv("donor_events.csv"):
    try:
        at = datetime.fromisoformat(ev["event_at"])
        if ev["donor_id"] not in _DEFER_EVENT_AT or at >= _DEFER_EVENT_AT[ev["donor_id"]]:
            _DEFER_EVENT_AT[ev["donor_id"]] = at
            DEFER_UNTIL[ev["donor_id"]] = datetime.fromisoformat(ev["defer_until"])
    except (ValueError, TypeError):
        continue

LOCK = threading.RLock()
REQ: dict[str, dict[str, Any]] = {}
IDEM: dict[str, tuple[str, int, dict[str, Any]]] = {}
SEEN_EVENTS: set[str] = set()
NOTIFICATION_STATE: dict[str, dict[str, Any]] = {}
DONOR_COMMITMENT: dict[str, tuple[str, str]] = {}
DONOR_PENDING_INVITE: dict[str, tuple[str, float]] = {}
NOTIFIED_COUNT: dict[str, int] = {d["donor_id"]: int(d.get("notified_90d", 0) or 0) for d in DONORS}
SIM = {"now": 0.0, "last_refresh": 0.0}
RATE: dict[str, list[float]] = {}
BURST_SIGNATURES: dict[tuple[str, str, str, int, str], list[float]] = {}
API_RATE: dict[str, list[float]] = {}


def sim_now() -> float:
    return float(SIM["now"])

def sim_datetime(minutes: float) -> datetime:
    return EPOCH + timedelta(minutes=float(minutes))

def json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def error(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}

def http_json(method: str, url: str, body: Any = None, headers: dict[str, str] | None = None, timeout: float = 3.0):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    hs = {"Content-Type": "application/json"}; hs.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=hs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read(); return res.status, (json.loads(raw) if raw else {}), dict(res.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try: payload = json.loads(raw) if raw else {}
        except Exception: payload = {}
        return exc.code, payload, dict(exc.headers)
    except Exception as exc:
        return 0, {"error": str(exc)}, {}

def http_json_retry(method: str, url: str, body: Any = None, headers: dict[str, str] | None = None, attempts: int = 4, timeout: float = 3.0):
    """Bounded retry for transient 429/503/network failures; reuses the same idempotency body."""
    for attempt in range(attempts):
        code, payload, response_headers = http_json(method, url, body, headers, timeout)
        if code not in (0, 429, 503) or attempt == attempts - 1:
            return code, payload, response_headers
        try: delay = float(next((v for k, v in response_headers.items() if k.lower() == "retry-after"), 1))
        except (TypeError, ValueError): delay = 1.0
        time.sleep(min(max(delay, 0.1), 2.0))
    return 0, {"error": {"code": "unavailable", "message": "retry attempts exhausted"}}, {}

def refresh_clock() -> None:
    code, payload, _ = http_json("GET", GATEWAY_URL + "/clock", timeout=1.5)
    if code == 200 and isinstance(payload, dict) and isinstance(payload.get("sim_time"), (int, float)):
        with LOCK:
            SIM["now"] = max(SIM["now"], float(payload["sim_time"]))
            SIM["last_refresh"] = time.monotonic()

def mark_wave_sent(nid: str, body: dict[str, Any]) -> None:
    """Count a request-wave notification once, including when it succeeds on outbox retry."""
    if body.get("template") != "request_wave": return
    with LOCK:
        st = NOTIFICATION_STATE.get(nid)
        if not st: return
        did = body.get("donor_id"); rid = body.get("request_id")
        if not st.get("counted"):
            NOTIFIED_COUNT[did] = NOTIFIED_COUNT.get(did, 0) + 1
            st["counted"] = True
        if not st.get("event_recorded"):
            r = REQ.get(rid)
            if r:
                suffix = nid.rsplit("-wave", 1)[-1]
                try: wave = int(suffix)
                except ValueError: wave = r.get("waves", 0) + 1
                r["events"].append({"type": "donor_notified", "donor_id": did, "sim_time": sim_now(), "wave": wave})
                if r["status"] == "open": r["status"] = "mobilizing"
            st["event_recorded"] = True

def gateway_post(body: dict[str, Any], attempts: int = 4) -> tuple[int, dict[str, Any]]:
    # Stable notification_id is supplied by caller and reused on retries.
    for attempt in range(attempts):
        code, payload, headers = http_json("POST", GATEWAY_URL + "/messages", body, timeout=4)
        if code == 202 or code == 409: return code, payload  # 409 means this stable id was already accepted
        if code not in (429, 503, 0) or attempt == attempts - 1: return code, payload
        try: delay = float(next((v for k, v in headers.items() if k.lower() == "retry-after"), 1))
        except (TypeError, ValueError): delay = 1.0
        time.sleep(min(max(delay, 0.1), 2.0))
    return 0, {"error": {"code": "unavailable", "message": "gateway retries exhausted"}}

def notify(donor_id: str, request_id: str, template: str, suffix: str) -> bool:
    nid = f"bn-{request_id}-{donor_id}-{suffix}"[:128]
    body = {"notification_id": nid, "donor_id": donor_id, "template": template,
            "request_id": request_id, "callback_url": SELF_URL}
    with LOCK:
        st = NOTIFICATION_STATE.get(nid)
        if st and st.get("accepted"): return True
        NOTIFICATION_STATE.setdefault(nid, {"body": body, "accepted": False, "attempts": 0, "counted": False, "event_recorded": False})
        NOTIFICATION_STATE[nid]["attempts"] += 1
    code, _ = gateway_post(body)
    ok = code in (202, 409)
    with LOCK:
        NOTIFICATION_STATE[nid]["accepted"] = ok
        NOTIFICATION_STATE[nid]["last_code"] = code
    if ok: mark_wave_sent(nid, body)
    return ok

def is_compatible(donor_group: str, recipient_group: str, product: str) -> bool:
    try: return donor_group in COMPAT[product][recipient_group]
    except (KeyError, TypeError): return False

def eligible(d: dict[str, str], product: str, ts: float) -> bool:
    try:
        age = int(d["age"]); weight = float(d["weight_kg"])
        if not (int(RULES["age_min"]) <= age <= int(RULES["age_max"])): return False
        if weight < float(RULES["weight_min_kg"]) or d["permanently_excluded"] == "1": return False
        defer = DEFER_UNTIL.get(d["donor_id"])
        if defer and sim_datetime(ts) < defer: return False
        if NOTIFIED_COUNT.get(d["donor_id"], int(d.get("notified_90d", "0"))) >= 6: return False
        last = d.get("last_donation_at", "")
        if last:
            since_days = (sim_datetime(ts) - datetime.fromisoformat(last)).total_seconds() / 86400.0
            target_type = {"red_cells": "whole_blood", "platelets": "platelets", "plasma": "plasma"}[product]
            previous = d.get("last_donation_type", "")
            if previous == target_type:
                if product == "red_cells": need = float(RULES["interval_wb_male"] if d["sex"] == "M" else RULES["interval_wb_female"])
                else: need = float(RULES["interval_apheresis"])
            else:
                need = float(RULES["cross_block"])
            if since_days < need: return False
        return True
    except (ValueError, KeyError, TypeError):
        return False

def quiet_now(d: dict[str, str], ts: float) -> bool:
    try:
        hour = int((ts % 1440) // 60)
        start, end = int(d["quiet_start_hour"]), int(d["quiet_end_hour"])
        if start == end: return False
        return (hour >= start or hour < end) if start > end else (start <= hour < end)
    except Exception: return False

def travel_score(d: dict[str, str], hospital_id: str) -> float:
    return TRAVEL_MIN.get((d.get("area_id", ""), hospital_id), 1e9)

def update_status(r: dict[str, Any]) -> None:
    if r["status"] in ("cancelled", "fulfilled", "expired", "pending_review"): return
    # In-transit stock is committed supply, not fulfilled supply. Only arrival/donation counts.
    if r["fulfilled"] >= r["needed"]: r["status"] = "fulfilled"
    elif r["fulfilled"] > 0: r["status"] = "partially_fulfilled"
    elif r["confirmed"] > 0 or r["en_route"] > 0 or r["stock_inflight"] > 0 or r.get("stock_reserved", 0) > 0: r["status"] = "mobilizing"
    else: r["status"] = "open"

def remaining_need(r: dict[str, Any]) -> int:
    active_donors = sum(1 for s in r["donors"].values() if s["state"] in ("accepted", "en_route", "arrived", "screen_pass"))
    return max(0, r["needed"] - r["fulfilled"] - r["stock_inflight"] - r.get("stock_reserved", 0) - active_donors)

def emit_cancel_pending(r: dict[str, Any], template: str) -> None:
    targets = []
    with LOCK:
        for did, state in list(r["donors"].items()):
            if state["state"] in ("notified", "accepted", "en_route", "arrived", "screen_pass"):
                was_committed = state["state"] != "notified"
                state["state"] = "stopped"
                if was_committed: targets.append(did)
                r["events"].append({"type": "donor_stopped", "donor_id": did, "sim_time": sim_now(), "reason": template})
                if DONOR_COMMITMENT.get(did) == (r["id"], did): DONOR_COMMITMENT.pop(did, None)
                if DONOR_PENDING_INVITE.get(did, (None,))[0] == r["id"]: DONOR_PENDING_INVITE.pop(did, None)
        stage_rank = {"notified": 0, "accepted": 1, "en_route": 2, "arrived": 3, "screen_pass": 4, "donated": 5,
                      "declined": 6, "screen_fail": 6, "no_show": 6, "stopped": 6}
        r["en_route"] = sum(1 for x in r["donors"].values() if stage_rank.get(x["state"], 0) >= 2 and x["state"] not in ("no_show", "screen_fail", "stopped"))
        r["arrived"] = sum(1 for x in r["donors"].values() if stage_rank.get(x["state"], 0) >= 3 and x["state"] not in ("no_show", "screen_fail", "stopped"))
    # Network I/O must not hold the shared state lock.
    for did in targets:
        notify(did, r["id"], template, f"{template}-v1")

def dispatch_stock(rid: str) -> None:
    with LOCK:
        r = REQ.get(rid)
        if not r or r["status"] in ("cancelled", "fulfilled", "expired", "pending_review"): return
        need = remaining_need(r)
        if need <= 0: update_status(r); return
        existing = r["dispatch_work"]
        if existing: return
        batch_id = "batch-" + uuid.uuid4().hex
        r["dispatch_work"] = batch_id
        r["dispatch_seq"] = r.get("dispatch_seq", 0) + 1
        dispatch_seq = r["dispatch_seq"]
        request_snapshot = dict(r)
    code, payload, _ = http_json_retry("GET", INVENTORY_URL + "/inventory", attempts=3, timeout=3)
    if code != 200 or not isinstance(payload, dict):
        with LOCK:
            if rid in REQ: REQ[rid]["dispatch_work"] = None
        return
    items = payload.get("items", [])
    eligible_items = [it for it in items if it.get("product") == request_snapshot["product"]
                      and is_compatible(it.get("blood_group", ""), request_snapshot["blood_group"], request_snapshot["product"])
                      and float(it.get("expires_sim_min", 1e18)) > sim_now()]
    eligible_items.sort(key=lambda it: (float(it.get("expires_sim_min", 1e18)), travel_center_to_hospital(it.get("center_id"), request_snapshot["hospital_id"])))
    picks = []; left = need
    for it in eligible_items:
        if left <= 0: break
        units = min(int(it.get("units", 0)), left)
        if units > 0:
            picks.append((it, units)); left -= units
    for idx, (it, planned_units) in enumerate(picks):
        with LOCK:
            current = REQ.get(rid)
            if not current or current["status"] in ("cancelled", "expired"):
                if current: current["dispatch_work"] = None
                return
            units = min(planned_units, remaining_need(current))
            if units <= 0: break
            # Reserve capacity before the network call so a concurrent donor acceptance
            # cannot commit the same remaining unit while Inventory is processing dispatch.
            current["stock_reserved"] = current.get("stock_reserved", 0) + units
        dispatch_id = f"dsp-{rid}-{dispatch_seq}-{it['center_id']}-{it['blood_group']}-{idx}"[:128]
        body = {"dispatch_id": dispatch_id, "request_id": rid, "center_id": it["center_id"],
                "blood_group": it["blood_group"], "product": request_snapshot["product"], "units": units,
                "hospital_id": request_snapshot["hospital_id"], "recipient_blood_group": request_snapshot["blood_group"]}
        c, result, _ = http_json_retry("POST", INVENTORY_URL + "/inventory/dispatch", body, attempts=4, timeout=4)
        with LOCK:
            current = REQ.get(rid)
            if not current: return
            current["stock_reserved"] = max(0, current.get("stock_reserved", 0) - units)
            if c in (200, 201):
                eta = result.get("eta_sim_min")
                if eta is not None and not any(x["dispatch_id"] == dispatch_id for x in current["stock_arrivals"]):
                    current["stock_arrivals"].append({"dispatch_id": dispatch_id, "units": units, "eta": float(eta)})
                    current["stock_inflight"] += units
                    current["events"].append({"type": "stock_dispatched", "sim_time": sim_now(), "units": units, "center_id": it["center_id"]})
                elif eta is None:
                    current["events"].append({"type": "dispatch_missing_eta", "sim_time": sim_now(), "dispatch_id": dispatch_id})
            elif c in (409, 422):
                current["events"].append({"type": "dispatch_rejected", "sim_time": sim_now(), "code": result.get("error", {}).get("code")})
        if c in (409, 422):
            # A concurrent request may have consumed this batch's stock snapshot.
            # A failed dispatch deducts nothing, so continue to the next FEFO pick.
            continue
        if c not in (200, 201): break
    with LOCK:
        if rid in REQ:
            REQ[rid]["dispatch_work"] = None
            update_status(REQ[rid])

def travel_center_to_hospital(center_id: str, hospital_id: str) -> float:
    # Static kit matrix is the deterministic fallback; live Travel service is queried for ETA tie-breaks.
    # This avoids exhausting the Travel quota while still respecting its 429 contract.
    return _CENTER_TRAVEL.get((center_id, hospital_id), 1e6)

_CENTER_TRAVEL: dict[tuple[str, str], float] = {}
try:
    with open(os.path.join(KIT_PATH, "travel_center_to_hospital.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("center_id") or row.get("center")
            for hid in HOSPITAL_BY_ID:
                try: _CENTER_TRAVEL[(cid, hid)] = float(row[hid])
                except (KeyError, ValueError): pass
except OSError: pass

_TRAVEL_CACHE: dict[tuple[str, str], float] = {}
_TRAVEL_CACHE_LOCK = threading.Lock()
def live_travel_minutes(donor_id: str, hospital_id: str) -> float | None:
    """Query the kit Travel service for a small shortlist; cache by donor/hospital."""
    key = (donor_id, hospital_id)
    with _TRAVEL_CACHE_LOCK:
        if key in _TRAVEL_CACHE: return _TRAVEL_CACHE[key]
    d = DONOR_BY_ID.get(donor_id); h = HOSPITAL_BY_ID.get(hospital_id)
    if not d or not h: return None
    query = urllib.parse.urlencode({"from": f"{d['lat']},{d['lon']}", "to": f"{h['lat']},{h['lon']}"})
    for attempt in range(3):
        code, payload, headers = http_json("GET", TRAVEL_URL + "/travel?" + query, timeout=2)
        if code == 200 and isinstance(payload, dict) and isinstance(payload.get("minutes"), (int, float)):
            value = float(payload["minutes"])
            with _TRAVEL_CACHE_LOCK: _TRAVEL_CACHE[key] = value
            return value
        if code != 429: break
        try: delay = float(next((v for k, v in headers.items() if k.lower() == "retry-after"), 1))
        except (TypeError, ValueError): delay = 1.0
        time.sleep(min(max(delay, 0.1), 1.0))
    return None

def donor_candidates(r: dict[str, Any], radius: float) -> list[tuple[float, str]]:
    now = sim_now(); out = []
    for d in DONORS:
        did = d["donor_id"]
        if did in r["notified"]: continue
        if not is_compatible(d["blood_group"], r["blood_group"], r["product"]): continue
        if not eligible(d, r["product"], now) or quiet_now(d, now): continue
        if DONOR_COMMITMENT.get(did): continue
        pending = DONOR_PENDING_INVITE.get(did)
        if pending and pending[0] != r["id"] and pending[1] > now: continue
        dist = travel_score(d, r["hospital_id"])
        if dist > radius: continue
        # Distance is the dominant factor; past notification fatigue is a penalty.
        hist = HISTORY_STATS.get(did, {})
        responded = hist.get("responded", 0)
        donated = hist.get("donated", 0)
        # Smoothed historical end-to-end success rate; low-sample donors stay near the population prior.
        reliability = (donated + 0.56) / (responded + 8.0)
        score = dist * 0.75 - reliability * 60.0 + NOTIFIED_COUNT.get(did, 0) * 3.0
        out.append((score, did))
    out.sort(key=lambda x: x[0])
    return out

def send_wave(rid: str) -> None:
    with LOCK:
        r = REQ.get(rid)
        if not r or r["status"] in ("pending_review", "cancelled", "fulfilled", "expired"): return
        need = remaining_need(r)
        if need <= 0: return
        wave = r["waves"] + 1
        radius_by_urgency = {"critical": [35.0, 50.0, 70.0, 90.0],
                             "urgent": [25.0, 40.0, 60.0, 80.0],
                             "planned": [20.0, 30.0, 45.0, 65.0]}
        radius = radius_by_urgency[r["urgency"]][min(wave - 1, 3)]
        cap = min(max(need * 3, 6), 24)
        snap = dict(r)
    candidates = donor_candidates(snap, radius)[:cap]
    # Refine only a tiny shortlist through the live Travel API; the published area matrix
    # remains the fallback when the service is rate-limited or temporarily unavailable.
    shortlist = candidates[:min(1, len(candidates))]
    refined = []
    for base_score, did in shortlist:
        live = live_travel_minutes(did, snap["hospital_id"])
        if live is not None:
            static_minutes = travel_score(DONOR_BY_ID[did], snap["hospital_id"])
            base_score = base_score + (live - static_minutes) * 0.75
        refined.append((base_score, did))
    candidates = sorted(refined + candidates[len(shortlist):], key=lambda x: x[0])
    sent_count = 0
    for _, did in candidates:
        with LOCK:
            r = REQ.get(rid)
            if not r or r["status"] in ("cancelled", "fulfilled", "expired"): break
            if remaining_need(r) <= 0: break
            if did in r["notified"] or DONOR_COMMITMENT.get(did): continue
            r["notified"].add(did)
            DONOR_PENDING_INVITE[did] = (rid, sim_now() + 60.0)
            r["donors"].setdefault(did, {"state": "notified", "stage_time": -1.0, "notification_id": f"bn-{rid}-{did}-wave{wave}"})
            r["donors"][did]["notification_id"] = f"bn-{rid}-{did}-wave{wave}"
        ok = notify(did, rid, "request_wave", f"wave{wave}")
        if not ok:
            # Keep it in notified set to prevent spam/repeated IDs; retry outbox handles transient errors.
            continue
        with LOCK:
            r = REQ.get(rid)
            if r:
                sent_count += 1
    with LOCK:
        r = REQ.get(rid)
        if r:
            r["waves"] = wave; r["last_wave"] = sim_now()
            if sent_count > 0: r["status"] = "mobilizing"

def retry_outbox() -> None:
    # Retry notifications that have not been acknowledged; stable IDs make this idempotent.
    with LOCK: pending = [(k, dict(v["body"])) for k, v in NOTIFICATION_STATE.items() if not v.get("accepted") and v.get("attempts", 0) < 8]
    for nid, body in pending:
        template = body.get("template"); rid = body.get("request_id"); did = body.get("donor_id")
        with LOCK:
            r = REQ.get(rid)
            donor_state = r["donors"].get(did) if r else None
            terminal = not r or r["status"] in ("cancelled", "fulfilled", "expired", "pending_review")
            if template == "request_wave" and (terminal or not donor_state or donor_state["state"] != "notified" or remaining_need(r) <= 0):
                NOTIFICATION_STATE[nid]["attempts"] = 8
                continue
            if template == "confirmed" and (terminal or not donor_state or donor_state["state"] not in ("accepted", "en_route", "arrived", "screen_pass")):
                NOTIFICATION_STATE[nid]["attempts"] = 8
                continue
        code, _ = gateway_post(body, attempts=2)
        with LOCK:
            if nid in NOTIFICATION_STATE:
                NOTIFICATION_STATE[nid]["attempts"] += 1
                NOTIFICATION_STATE[nid]["accepted"] = code in (202, 409)
                NOTIFICATION_STATE[nid]["last_code"] = code
        if code in (202, 409): mark_wave_sent(nid, body)

def process_due_stock() -> None:
    now = sim_now(); to_stop = []
    with LOCK:
        for r in REQ.values():
            for a in list(r["stock_arrivals"]):
                if a["eta"] <= now:
                    r["stock_inflight"] = max(0, r["stock_inflight"] - a["units"])
                    r["fulfilled"] += a["units"]
                    r["stock_arrivals"].remove(a)
                    r["events"].append({"type": "stock_arrived", "sim_time": now, "units": a["units"]})
            update_status(r)
            if r["status"] not in ("cancelled", "expired", "pending_review") and r["fulfilled"] + r["stock_inflight"] >= r["needed"]:
                to_stop.append(r)
    for r in to_stop:
        emit_cancel_pending(r, "not_needed")

def background_loop() -> None:
    while True:
        refresh_clock()
        process_due_stock()
        now = sim_now()
        to_cancel = []
        with LOCK:
            priority = {"critical": 0, "urgent": 1, "planned": 2}
            ids = sorted(REQ, key=lambda rid: (priority.get(REQ[rid]["urgency"], 9), REQ[rid]["created"]))
            to_wave = []
            for rid in ids:
                r = REQ[rid]
                # Gateway's donor simulator expires an unconfirmed acceptance after 120 sim minutes.
                # Mirror that timeout so a donor is not committed forever if a callback is lost.
                for did, donor_state in r["donors"].items():
                    if donor_state["state"] == "accepted" and now - float(donor_state.get("stage_time", now)) > 120.0:
                        donor_state["state"] = "no_show"
                        donor_state["stage_time"] = now
                        r["events"].append({"type": "donor_no_show", "donor_id": did, "sim_time": now, "reason": "confirmation_timeout"})
                        if DONOR_COMMITMENT.get(did) == (rid, did): DONOR_COMMITMENT.pop(did, None)
                if r["status"] in ("cancelled", "fulfilled", "expired", "pending_review"): continue
                if now - r["created"] > float(RULES["sla"].get(r["urgency"], 1440)) and r["fulfilled"] < r["needed"]:
                    r["status"] = "expired"; to_cancel.append(r); continue
                wave_interval = {"critical": 15.0, "urgent": 30.0, "planned": 60.0}.get(r["urgency"], 45.0)
                if r["waves"] < 4 and now - r["last_wave"] >= wave_interval and remaining_need(r) > 0:
                    to_wave.append(rid)
        for r in to_cancel:
            emit_cancel_pending(r, "cancelled")
        for rid in ids:
            dispatch_stock(rid)
        for rid in to_wave:
            send_wave(rid)
        retry_outbox()
        time.sleep(1.0)


def abuse_review_needed(hospital_id: str, blood_group: str, product: str, units: int, urgency: str) -> bool:
    # Generic review gate: extreme single demand, repeated identical demand fingerprints,
    # or a high request burst at one hospital. No hospital ID is hard-coded.
    now = sim_now()
    if units >= 8 and urgency == "critical": return True
    signature = (hospital_id, blood_group, product, units, urgency)
    with LOCK:
        same = [t for t in BURST_SIGNATURES.get(signature, []) if now - t <= 60]
        BURST_SIGNATURES[signature] = same + [now]
        hist = [t for t in RATE.get(hospital_id, []) if now - t <= 60]
        RATE[hospital_id] = hist + [now]
        return len(same) >= 2 or len(hist) >= 5

class Handler(BaseHTTPRequestHandler):
    server_version = "BloodNetAPI/1.0"
    def log_message(self, *args): pass
    def send_json(self, code: int, body: Any, headers: dict[str, str] | None = None):
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", os.getenv("CORS_ORIGIN", "*"))
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, Idempotency-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        for k, v in (headers or {}).items(): self.send_header(k, str(v))
        self.send_header("Content-Length", str(len(raw))); self.end_headers()
        try: self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError): pass
    def read_body(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n < 0 or n > 1_000_000: return None
            raw = self.rfile.read(n) if n else b"{}"
            value = json.loads(raw.decode("utf-8"))
            return value if isinstance(value, dict) else None
        except Exception: return None
    def authorized(self, token: str) -> bool:
        return self.headers.get("Authorization", "") == f"Bearer {token}"
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", os.getenv("CORS_ORIGIN", "*"))
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, Idempotency-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/health":
            refresh_clock(); return self.send_json(200, {"ok": True, "service": "bloodnet", "sim_time": round(sim_now(), 3)})
        if path == "/meta":
            return self.send_json(200, {"hospitals": [{"hospital_id": h["hospital_id"], "name": h["name"]} for h in HOSPITAL_ROWS],
                                       "centers": [{"center_id": c["center_id"], "name": c["name"]} for c in CENTERS.values()],
                                       "blood_groups": GROUPS, "products": PRODUCTS, "urgencies": URGENCIES})
        if path == "/requests":
            if not self.authorized(HOSPITAL_TOKEN) and not self.authorized(COORDINATOR_TOKEN): return self.send_json(401, error("unauthorized", "Hospital or coordinator token required"))
            with LOCK:
                rows = []
                for r in sorted(REQ.values(), key=lambda x: (x["created"]), reverse=True):
                    rows.append({"request_id": r["id"], "hospital_id": r["hospital_id"], "blood_group": r["blood_group"],
                                 "product": r["product"], "urgency": r["urgency"], "needed": r["needed"],
                                 "fulfilled": r["fulfilled"], "remaining": max(0, r["needed"] - r["fulfilled"]),
                                 "stock_inflight": r["stock_inflight"], "stock_reserved": r.get("stock_reserved", 0), "confirmed": r["confirmed"],
                                 "status": r["status"], "created_sim_min": round(r["created"], 2)})
            return self.send_json(200, {"items": rows})
        if path == "/inventory":
            if not self.authorized(COORDINATOR_TOKEN) and not self.authorized(HOSPITAL_TOKEN):
                return self.send_json(401, error("unauthorized", "Hospital or coordinator token required"))
            code, payload, headers = http_json_retry("GET", INVENTORY_URL + "/inventory", attempts=3, timeout=3)
            if code != 200: return self.send_json(503, error("inventory_unavailable", "Inventory service is temporarily unavailable"), {"Retry-After": "2"})
            return self.send_json(200, payload)
        if path.startswith("/requests/") and path.endswith("/events"):
            if not self.authorized(HOSPITAL_TOKEN) and not self.authorized(COORDINATOR_TOKEN): return self.send_json(401, error("unauthorized", "Hospital or coordinator token required"))
            rid = urllib.parse.unquote(path.strip("/").split("/")[1])
            with LOCK:
                r = REQ.get(rid)
                if not r: return self.send_json(404, error("not_found", "Request not found"))
                return self.send_json(200, {"items": list(r["events"])})
        if path.startswith("/donors/") and path.endswith("/invitations"):
            if not self.authorized(DONOR_DEMO_TOKEN): return self.send_json(401, error("unauthorized", "Donor demo token required"))
            did = urllib.parse.unquote(path.strip("/").split("/")[1])
            if did not in DONOR_BY_ID: return self.send_json(404, error("unknown_donor", "Donor is not registered in the synthetic kit"))
            with LOCK:
                items = []
                for r in REQ.values():
                    if did in r["donors"]:
                        st = r["donors"][did]
                        items.append({"request_id": r["id"], "hospital_id": r["hospital_id"], "product": r["product"],
                                      "blood_group": r["blood_group"], "urgency": r["urgency"], "status": r["status"],
                                      "invitation_state": st["state"], "needed": r["needed"], "fulfilled": r["fulfilled"]})
            return self.send_json(200, {"donor_id": did, "items": items})
        if path.startswith("/requests/") and path.count("/") == 2:
            if not self.authorized(HOSPITAL_TOKEN) and not self.authorized(COORDINATOR_TOKEN): return self.send_json(401, error("unauthorized", "Hospital or coordinator token required"))
            rid = urllib.parse.unquote(path.split("/")[2])
            with LOCK:
                r = REQ.get(rid)
                if not r: return self.send_json(404, error("not_found", "Request not found"))
                payload = {"request_id": rid, "status": r["status"], "needed": r["needed"], "confirmed": r["confirmed"],
                           "en_route": r["en_route"], "arrived": r["arrived"], "fulfilled": r["fulfilled"],
                           "hospital_id": r["hospital_id"], "blood_group": r["blood_group"], "product": r["product"],
                           "urgency": r["urgency"], "stock_inflight": r["stock_inflight"], "stock_reserved": r.get("stock_reserved", 0),
                           "created_sim_min": round(r["created"], 2)}
                return self.send_json(200, payload)
        return self.send_json(404, error("not_found", "Endpoint not found"))
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        body = self.read_body()
        if path in ("/demo/donor-response", "/demo/donor-progress"):
            if not self.authorized(DONOR_DEMO_TOKEN): return self.send_json(401, error("unauthorized", "Donor demo token required"))
            if body is None or not isinstance(body.get("request_id"), str) or not isinstance(body.get("donor_id"), str):
                return self.send_json(400, error("validation_error", "request_id and donor_id are required"))
            if path.endswith("donor-response"):
                response = body.get("response")
                if response not in ("accepted", "declined"): return self.send_json(400, error("validation_error", "response must be accepted or declined"))
                with LOCK:
                    request = REQ.get(body["request_id"])
                    donor_state = request["donors"].get(body["donor_id"]) if request else None
                    if not donor_state or donor_state["state"] != "notified":
                        return self.send_json(409, error("invitation_not_active", "No active invitation for this donor and request"))
                    notification_id = donor_state["notification_id"]
                callback = {"event_id": "demo-" + uuid.uuid4().hex, "request_id": body["request_id"], "donor_id": body["donor_id"],
                            "notification_id": notification_id, "response": response, "sim_time": sim_now()}
                code, payload, _ = http_json_retry("POST", SELF_URL + "/callbacks/donor-response", callback, attempts=2, timeout=3)
            else:
                event = body.get("event")
                if event not in ("en_route", "arrived", "screen_pass", "screen_fail", "donated", "no_show"):
                    return self.send_json(400, error("validation_error", "Invalid donor progress event"))
                callback = {"event_id": "demo-" + uuid.uuid4().hex, "request_id": body["request_id"], "donor_id": body["donor_id"],
                            "event": event, "sim_time": sim_now()}
                code, payload, _ = http_json_retry("POST", SELF_URL + "/callbacks/donor-progress", callback, attempts=2, timeout=3)
            if code != 200: return self.send_json(503, error("callback_unavailable", "Could not record donor action"))
            return self.send_json(200, {"ok": True, "recorded": True})
        if path == "/requests": return self.create_request(body)
        if path.startswith("/callbacks/"): return self.callback(path, body)
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "requests":
            if not self.authorized(HOSPITAL_TOKEN) and parts[2] != "approve": return self.send_json(401, error("unauthorized", "Hospital token required"))
            rid, action = urllib.parse.unquote(parts[1]), parts[2]
            if action == "approve" and not self.authorized(COORDINATOR_TOKEN): return self.send_json(401, error("unauthorized", "Coordinator token required"))
            if action == "cancel": return self.cancel_request(rid)
            if action == "amend": return self.amend_request(rid, body)
            if action == "approve": return self.approve_request(rid, body)
        return self.send_json(404, error("not_found", "Endpoint not found"))
    def create_request(self, body: Any):
        if not self.authorized(HOSPITAL_TOKEN): return self.send_json(401, error("unauthorized", "Hospital token required"))
        key = self.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 128: return self.send_json(400, error("missing_idempotency_key", "Idempotency-Key header is required (max 128 chars)"))
        if body is None: return self.send_json(400, error("validation_error", "A valid JSON object is required"))
        allowed = {"hospital_id", "blood_group", "product", "units", "urgency", "note"}
        if set(body) - allowed: return self.send_json(400, error("validation_error", "Unexpected request fields"))
        if not all(k in body for k in ("hospital_id", "blood_group", "product", "units", "urgency")):
            return self.send_json(400, error("validation_error", "Required fields: hospital_id, blood_group, product, units, urgency"))
        if any(not isinstance(body[k], str) for k in ("hospital_id", "blood_group", "product", "urgency")):
            return self.send_json(400, error("validation_error", "hospital_id, blood_group, product and urgency must be strings"))
        if body["hospital_id"] not in HOSPITAL_BY_ID: return self.send_json(404, error("unknown_hospital", "Hospital is not registered in the participant kit"))
        if body["blood_group"] not in GROUPS or body["product"] not in PRODUCTS or body["urgency"] not in URGENCIES:
            return self.send_json(400, error("validation_error", "Invalid blood_group, product or urgency"))
        units = body["units"]
        if isinstance(units, bool) or not isinstance(units, int) or not 1 <= units <= 20:
            return self.send_json(400, error("validation_error", "units must be an integer from 1 to 20"))
        if "note" in body and (not isinstance(body["note"], str) or len(body["note"]) > 500):
            return self.send_json(400, error("validation_error", "note must be a string of at most 500 characters"))
        digest = json_hash(body)
        with LOCK:
            if key in IDEM:
                old_hash, old_code, old_payload = IDEM[key]
                if old_hash != digest: return self.send_json(422, error("idempotency_key_reuse", "Idempotency-Key was already used with a different body"))
                return self.send_json(200, old_payload)
            now = sim_now()
            recent = [t for t in API_RATE.get(body["hospital_id"], []) if now - t < 1.0]
            if len(recent) >= 120:
                API_RATE[body["hospital_id"]] = recent
                return self.send_json(429, error("rate_limited", "Too many request creations; retry with the same Idempotency-Key"), {"Retry-After": "1"})
            API_RATE[body["hospital_id"]] = recent + [now]
            review = abuse_review_needed(body["hospital_id"], body["blood_group"], body["product"], units, body["urgency"])
            rid = "R-" + uuid.uuid4().hex[:12]
            status = "pending_review" if review else "open"
            r = {"id": rid, "hospital_id": body["hospital_id"], "blood_group": body["blood_group"], "product": body["product"],
                 "urgency": body["urgency"], "needed": units, "note": body.get("note", ""), "status": status,
                 "confirmed": 0, "en_route": 0, "arrived": 0, "fulfilled": 0, "stock_inflight": 0, "stock_reserved": 0,
                 "created": sim_now(), "last_wave": sim_now() - 60.0, "waves": 0, "notified": set(), "donors": {},
                 "stock_arrivals": [], "dispatch_work": None, "dispatch_seq": 0,
                 "events": [{"type": "request_created", "sim_time": sim_now()}]}
            REQ[rid] = r
            payload = {"request_id": rid, "status": status, "needed": units}
            IDEM[key] = (digest, 201, payload)
        # Keep the API response fast and let the background worker contact the external
        # simulators. The first wave is marked due immediately; the runner registers its
        # ground-truth request after receiving this 201 response.
        return self.send_json(201, payload)
    def cancel_request(self, rid: str):
        should_stop = False
        with LOCK:
            r = REQ.get(rid)
            if not r: return self.send_json(404, error("not_found", "Request not found"))
            if r["status"] not in ("cancelled", "fulfilled", "expired"):
                r["status"] = "cancelled"; r["events"].append({"type": "cancelled", "sim_time": sim_now()})
                should_stop = True
            status = r["status"]
        if should_stop: emit_cancel_pending(r, "cancelled")
        return self.send_json(200, {"request_id": rid, "status": status})
    def amend_request(self, rid: str, body: Any):
        if body is None or set(body) != {"urgency"} or body.get("urgency") not in URGENCIES:
            return self.send_json(400, error("validation_error", "urgency must be critical, urgent or planned"))
        with LOCK:
            r = REQ.get(rid)
            if not r: return self.send_json(404, error("not_found", "Request not found"))
            if r["status"] in ("cancelled", "fulfilled", "expired", "pending_review"):
                return self.send_json(409, error("not_amendable", "Request is not amendable in its current state"))
            r["urgency"] = body["urgency"]; r["events"].append({"type": "urgency_amended", "sim_time": sim_now(), "urgency": body["urgency"]})
        return self.send_json(200, {"request_id": rid, "urgency": body["urgency"]})
    def approve_request(self, rid: str, body: Any):
        if body is not None and set(body) - {"approved", "note"}: return self.send_json(400, error("validation_error", "Unexpected approval fields"))
        if body and "approved" in body and not isinstance(body["approved"], bool):
            return self.send_json(400, error("validation_error", "approved must be a boolean"))
        if body and "note" in body and (not isinstance(body["note"], str) or len(body["note"]) > 500):
            return self.send_json(400, error("validation_error", "note must be a string of at most 500 characters"))
        approved = body.get("approved", True) if body else True
        note = (body or {}).get("note", "").strip()
        if not approved and not note:
            return self.send_json(400, error("rejection_note_required", "A reason is required when rejecting a request"))
        should_stop = False
        with LOCK:
            r = REQ.get(rid)
            if not r: return self.send_json(404, error("not_found", "Request not found"))
            if r["status"] != "pending_review": return self.send_json(409, error("not_pending_review", "Request is not awaiting review"))
            if approved:
                r["status"] = "open"
                r["last_wave"] = sim_now() - 60.0
                r["events"].append({"type": "approved", "sim_time": sim_now(), "note": note})
                result_status = "open"
            else:
                r["status"] = "cancelled"
                r["events"].append({"type": "review_rejected", "sim_time": sim_now(), "note": note})
                should_stop = True
                result_status = "cancelled"
        if should_stop: emit_cancel_pending(r, "review_rejected")
        return self.send_json(200, {"request_id": rid, "status": result_status, "decision": "approved" if approved else "rejected"})
    def callback(self, path: str, body: Any):
        if body is None: return self.send_json(400, error("validation_error", "A valid JSON object is required"))
        kind = path.rsplit("/", 1)[-1]
        required = {
            "donor-response": ("event_id", "request_id", "donor_id", "notification_id", "response", "sim_time"),
            "donor-progress": ("event_id", "request_id", "donor_id", "event", "sim_time"),
            "gateway-status": ("event_id", "notification_id", "request_id", "donor_id", "status", "sim_time")
        }.get(kind)
        if not required: return self.send_json(404, error("not_found", "Unknown callback"))
        if any(k not in body for k in required): return self.send_json(400, error("validation_error", "Missing callback fields"))
        string_fields = [k for k in required if k != "sim_time"]
        if any(not isinstance(body[k], str) or not body[k] for k in string_fields):
            return self.send_json(400, error("validation_error", "Callback identifiers and state fields must be non-empty strings"))
        if isinstance(body["sim_time"], bool) or not isinstance(body["sim_time"], (int, float)):
            return self.send_json(400, error("validation_error", "Invalid sim_time"))
        if "reason" in body and not isinstance(body["reason"], str):
            return self.send_json(400, error("validation_error", "reason must be a string"))
        allowed = {"donor-response": {"accepted", "declined"}, "donor-progress": {"en_route", "arrived", "screen_pass", "screen_fail", "donated", "no_show"},
                   "gateway-status": {"queued", "sent", "delivered", "failed", "expired"}}
        field = {"donor-response": "response", "donor-progress": "event", "gateway-status": "status"}[kind]
        if body[field] not in allowed[kind]: return self.send_json(400, error("validation_error", "Invalid callback state"))
        with LOCK:
            if body["event_id"] in SEEN_EVENTS: return self.send_json(200, {"ok": True, "duplicate": True})
            r = REQ.get(body["request_id"])
            if not r:
                SEEN_EVENTS.add(body["event_id"])
                return self.send_json(200, {"ok": True, "ignored": True})
            did = body.get("donor_id")
            if kind == "donor-response":
                n = NOTIFICATION_STATE.get(body["notification_id"])
                if (did not in r["donors"] or not n or n["body"].get("template") != "request_wave"
                    or n["body"].get("request_id") != r["id"] or n["body"].get("donor_id") != did):
                    SEEN_EVENTS.add(body["event_id"])
                    return self.send_json(200, {"ok": True, "ignored": True})
            elif kind == "gateway-status":
                n = NOTIFICATION_STATE.get(body["notification_id"])
                if (not n or n["body"].get("request_id") != r["id"] or n["body"].get("donor_id") != did):
                    SEEN_EVENTS.add(body["event_id"])
                    return self.send_json(200, {"ok": True, "ignored": True})
            elif did not in r["donors"]:
                SEEN_EVENTS.add(body["event_id"])
                return self.send_json(200, {"ok": True, "ignored": True})
            SEEN_EVENTS.add(body["event_id"])
            if kind == "gateway-status":
                n = NOTIFICATION_STATE.get(body["notification_id"])
                if n:
                    rank = {"queued": 1, "sent": 2, "delivered": 3, "failed": 4, "expired": 4}
                    old = n.get("gateway_status")
                    if old is None or rank[body["status"]] >= rank[old]: n["gateway_status"] = body["status"]
                gateway_event = {"type": "gateway_" + body["status"], "sim_time": float(body["sim_time"]), "donor_id": did}
                if body.get("reason"): gateway_event["reason"] = body["reason"]
                r["events"].append(gateway_event)
            elif kind == "donor-response":
                state = r["donors"][did]
                if body["response"] == "accepted":
                    if DONOR_PENDING_INVITE.get(did, (None,))[0] == r["id"]: DONOR_PENDING_INVITE.pop(did, None)
                    if state["state"] == "notified":
                        if r["status"] in ("cancelled", "fulfilled", "expired") or remaining_need(r) <= 0 or DONOR_COMMITMENT.get(did):
                            state["state"] = "stopped"
                            should_not_need = True
                        else:
                            state["state"] = "accepted"; state["stage_time"] = float(body["sim_time"])
                            DONOR_COMMITMENT[did] = (r["id"], did); r["confirmed"] += 1
                            should_not_need = False
                    else: should_not_need = False
                else:
                    if DONOR_PENDING_INVITE.get(did, (None,))[0] == r["id"]: DONOR_PENDING_INVITE.pop(did, None)
                    if state["state"] == "notified": state["state"] = "declined"
                    should_not_need = False
                response_event = {"type": "donor_" + body["response"], "sim_time": float(body["sim_time"]), "donor_id": did}
                if body.get("reason"): response_event["reason"] = body["reason"]
                r["events"].append(response_event)
                if body["response"] == "accepted" and not should_not_need:
                    threading.Thread(target=notify, args=(did, r["id"], "confirmed", "confirmed-v1"), daemon=True).start()
                elif should_not_need:
                    threading.Thread(target=notify, args=(did, r["id"], "not_needed", "not-needed-v1"), daemon=True).start()
            else:
                state = r["donors"].get(did)
                if not state: return self.send_json(200, {"ok": True, "ignored": True})
                event = body["event"]; ts = float(body["sim_time"])
                terminal = ("declined", "screen_fail", "no_show", "stopped", "donated")
                stage_rank = {"notified": 0, "accepted": 1, "en_route": 2, "arrived": 3, "screen_pass": 4,
                              "donated": 5, "declined": 6, "screen_fail": 6, "no_show": 6, "stopped": 6}
                previous_time = float(state.get("stage_time", -1.0))
                current_state = state["state"]
                # Callback arrival order is not event order. The Gateway sim_time is authoritative.
                # Enforce both monotonic event time and monotonic lifecycle stage.
                valid_transition = (ts >= previous_time and current_state not in terminal
                                    and stage_rank[event] >= stage_rank.get(current_state, 0))
                if event == "screen_fail" and current_state in ("screen_pass", "donated"): valid_transition = False
                if event == "no_show" and current_state in ("arrived", "screen_pass", "donated"): valid_transition = False
                if event == "donated" and current_state in ("screen_fail", "no_show", "declined", "stopped"): valid_transition = False
                if valid_transition:
                    state["state"] = event; state["stage_time"] = ts
                    progress_event = {"type": "donor_" + event, "sim_time": ts, "donor_id": did}
                    if body.get("reason"): progress_event["reason"] = body["reason"]
                    r["events"].append(progress_event)
                    if event in ("no_show", "screen_fail"):
                        if DONOR_COMMITMENT.get(did) == (r["id"], did): DONOR_COMMITMENT.pop(did, None)
                        if DONOR_PENDING_INVITE.get(did, (None,))[0] == r["id"]: DONOR_PENDING_INVITE.pop(did, None)
                    if event == "donated":
                        # Only the donated event counts; a donor contributes at most one unit.
                        if not state.get("counted_donation"):
                            state["counted_donation"] = True; r["fulfilled"] += 1
                        if DONOR_COMMITMENT.get(did) == (r["id"], did): DONOR_COMMITMENT.pop(did, None)
                        if DONOR_PENDING_INVITE.get(did, (None,))[0] == r["id"]: DONOR_PENDING_INVITE.pop(did, None)
                        update_status(r)
                        if r["fulfilled"] + r["stock_inflight"] >= r["needed"]:
                            threading.Thread(target=emit_cancel_pending, args=(r, "not_needed"), daemon=True).start()
                stage_rank = {"notified": 0, "accepted": 1, "en_route": 2, "arrived": 3, "screen_pass": 4, "donated": 5,
                              "declined": 6, "screen_fail": 6, "no_show": 6, "stopped": 6}
                r["en_route"] = sum(1 for x in r["donors"].values() if stage_rank.get(x["state"], 0) >= 2 and x["state"] not in ("no_show", "screen_fail", "stopped"))
                r["arrived"] = sum(1 for x in r["donors"].values() if stage_rank.get(x["state"], 0) >= 3 and x["state"] not in ("no_show", "screen_fail", "stopped"))
                update_status(r)
        return self.send_json(200, {"ok": True})


def run():
    from http.server import ThreadingHTTPServer
    from harness.common import make_server
    refresh_clock()
    threading.Thread(target=background_loop, daemon=True, name="bloodnet-background").start()
    server = make_server(PORT, Handler)
    print(f"BloodNet API listening on http://127.0.0.1:{PORT}")
    server.serve_forever()

if __name__ == "__main__": run()
