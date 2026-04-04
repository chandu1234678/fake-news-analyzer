"""
Stress Test — FactChecker AI Backend

Tests:
  1. Health check
  2. Input validation — oversized body, bad email, short password
  3. Auth security — invalid tokens, tampered JWT, SQL injection
  4. Rate limiting — verify 429 fires correctly
  5. Concurrent load — 20 parallel requests

Run: python backend/tests/stress_test.py [base_url]
Default: http://127.0.0.1:8000
"""

import sys
import time
import json
import threading
import urllib.request
import urllib.error
import ssl

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PASS = "✅"
FAIL = "❌"

# Allow self-signed certs in test
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def req(method, path, body=None, token=None, timeout=20):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout, context=_ctx) as resp:
            return resp.status, json.loads(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        try:
            body_data = json.loads(e.read())
        except Exception:
            body_data = {}
        return e.code, body_data, dict(e.headers)
    except Exception as e:
        return 0, {"error": str(e)}, {}


results = []


def test(name, passed, detail=""):
    icon = PASS if passed else FAIL
    print(f"  {icon} {name}" + (f"  [{detail}]" if detail else ""))
    results.append(passed)
    return passed


print(f"\n🔍 Stress testing {BASE}\n")

# ── 1. Health ─────────────────────────────────────────────────
print("── Health")
s, d, h = req("GET", "/health")
test("Health returns 200", s == 200, f"status={s}")
test("Health has version field", "version" in d or "status" in d, str(d))

# ── 2. Input Validation ───────────────────────────────────────
print("\n── Input Validation")

s, d, _ = req("POST", "/auth/signup", {"email": "test@test.com", "password": "abc", "name": "T"})
test("Short password rejected (400/422)", s in (400, 422), f"got {s}: {d.get('detail','')}")

s, d, _ = req("POST", "/auth/signup", {"email": "notanemail", "password": "password123"})
test("Invalid email rejected (422)", s in (400, 422), f"got {s}")

s, d, _ = req("POST", "/auth/login", {"email": "test@test.com", "password": ""})
test("Empty password rejected", s in (400, 401, 422), f"got {s}")

s, d, _ = req("POST", "/message", {"message": "x" * 2001})
test("Message >2000 chars rejected", s in (400, 401, 422), f"got {s}: {d.get('detail','')}")

s, d, _ = req("POST", "/message", {"message": ""})
test("Empty message rejected", s in (400, 401, 422), f"got {s}")

# ── 3. Auth Security ──────────────────────────────────────────
print("\n── Auth Security")

s, d, _ = req("GET", "/auth/me")
test("No token → 401", s == 401, f"got {s}")

s, d, _ = req("GET", "/auth/me", token="garbage.token.here")
test("Garbage token → 401", s == 401, f"got {s}")

tampered = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.TAMPERED_SIG"
s, d, _ = req("GET", "/auth/me", token=tampered)
test("Tampered JWT → 401", s == 401, f"got {s}")

s, d, _ = req("POST", "/auth/login", {"email": "' OR 1=1--@x.com", "password": "pass"})
test("SQL injection in email → rejected", s in (400, 401, 422), f"got {s}")

s, d, _ = req("POST", "/auth/login", {"email": "<script>alert(1)</script>@x.com", "password": "pass"})
test("XSS in email → rejected", s in (400, 401, 422), f"got {s}")

# ── 4. Rate Limiting ──────────────────────────────────────────
print("\n── Rate Limiting")

hit_429 = False
for i in range(12):
    s, _, _ = req("POST", "/auth/login", {"email": f"spam{i}@test.com", "password": "wrongpass"})
    if s == 429:
        hit_429 = True
        break
test("Login rate limit fires (429)", hit_429, f"after {i+1} requests")

hit_429_otp = False
for i in range(7):
    s, _, _ = req("POST", "/auth/forgot-password", {"email": "spam@test.com"})
    if s == 429:
        hit_429_otp = True
        break
test("OTP rate limit fires (429)", hit_429_otp, f"after {i+1} requests")

# ── 5. Concurrent Load ────────────────────────────────────────
print("\n── Concurrent Load (20 parallel /health)")

responses = []
lock = threading.Lock()

def fire():
    s, _, _ = req("GET", "/health", timeout=20)
    with lock:
        responses.append(s)

threads = [threading.Thread(target=fire) for _ in range(20)]
t0 = time.time()
for t in threads: t.start()
for t in threads: t.join()
elapsed = time.time() - t0

ok = sum(1 for s in responses if s == 200)
test(f"20 concurrent requests — {ok}/20 OK in {elapsed:.1f}s", ok >= 18)

# ── 6. Endpoint existence ─────────────────────────────────────
print("\n── Endpoint Existence")
for path, method in [
    ("/health", "GET"),
    ("/auth/login", "POST"),
    ("/auth/signup", "POST"),
    ("/auth/forgot-password", "POST"),
    ("/credibility", "GET"),
    ("/stats/system", "GET"),
    ("/stats/calibration", "GET"),
]:
    s, _, _ = req(method, path, body={} if method == "POST" else None)
    test(f"{method} {path} reachable", s not in (0, 404, 500), f"got {s}")

# ── Summary ───────────────────────────────────────────────────
passed = sum(results)
total  = len(results)
print(f"\n{'='*50}")
print(f"  Results: {passed}/{total} passed")
if passed == total:
    print("  ✅ All tests passed")
elif passed >= total * 0.85:
    print(f"  ⚠️  {total-passed} minor failure(s) — mostly passing")
else:
    print(f"  ❌ {total-passed} test(s) failed — review above")
print(f"{'='*50}\n")
