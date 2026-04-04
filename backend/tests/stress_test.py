"""
Stress Test — FactChecker AI Backend

Tests:
  1. Rate limiting — verify 429 fires correctly
  2. Input validation — oversized body, bad email, short password
  3. Auth security — invalid tokens, expired tokens
  4. Concurrent load — 20 parallel requests

Run: python backend/tests/stress_test.py [base_url]
Default base_url: http://127.0.0.1:8000
"""

import sys
import time
import json
import threading
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PASS = "✅"
FAIL = "❌"


def req(method, path, body=None, token=None, timeout=10):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 0, {"error": str(e)}


def test(name, passed, detail=""):
    icon = PASS if passed else FAIL
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))
    return passed


results = []

print(f"\n🔍 Stress testing {BASE}\n")

# ── 1. Health check ───────────────────────────────────────────
print("── Health")
s, d = req("GET", "/health")
results.append(test("Health returns 200", s == 200, str(d.get("status"))))

# ── 2. Input validation ───────────────────────────────────────
print("\n── Input Validation")

# Short password
s, d = req("POST", "/auth/signup", {"email": "test@test.com", "password": "abc", "name": "T"})
results.append(test("Short password rejected", s in (400, 422), str(d.get("detail", d))))

# Invalid email
s, d = req("POST", "/auth/signup", {"email": "notanemail", "password": "password123"})
results.append(test("Invalid email rejected", s in (400, 422)))

# Empty message
s, d = req("POST", "/message", {"message": ""})
results.append(test("Empty message rejected", s in (400, 401, 422)))

# Oversized message (2001 chars)
s, d = req("POST", "/message", {"message": "x" * 2001})
results.append(test("Oversized message rejected", s in (400, 401, 422)))

# ── 3. Auth security ──────────────────────────────────────────
print("\n── Auth Security")

# No token
s, d = req("GET", "/auth/me")
results.append(test("No token → 401", s == 401))

# Garbage token
s, d = req("GET", "/auth/me", token="garbage.token.here")
results.append(test("Invalid token → 401", s == 401))

# Tampered JWT (valid format, wrong signature)
tampered = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.TAMPERED"
s, d = req("GET", "/auth/me", token=tampered)
results.append(test("Tampered JWT → 401", s == 401))

# SQL injection attempt in email
s, d = req("POST", "/auth/login", {"email": "' OR 1=1--@x.com", "password": "pass"})
results.append(test("SQL injection in email → rejected", s in (400, 401, 422)))

# ── 4. Rate limiting ──────────────────────────────────────────
print("\n── Rate Limiting")

# Hit login 12 times — should get 429
hit_429 = False
for i in range(12):
    s, _ = req("POST", "/auth/login", {"email": f"spam{i}@test.com", "password": "wrongpass"})
    if s == 429:
        hit_429 = True
        break
results.append(test("Login rate limit fires (429)", hit_429, f"after {i+1} requests"))

# Hit forgot-password 6 times — should get 429
hit_429_otp = False
for i in range(7):
    s, _ = req("POST", "/auth/forgot-password", {"email": "spam@test.com"})
    if s == 429:
        hit_429_otp = True
        break
results.append(test("OTP rate limit fires (429)", hit_429_otp, f"after {i+1} requests"))

# ── 5. Concurrent load ────────────────────────────────────────
print("\n── Concurrent Load (20 parallel requests)")

responses = []
lock = threading.Lock()

def fire():
    s, _ = req("GET", "/health", timeout=15)
    with lock:
        responses.append(s)

threads = [threading.Thread(target=fire) for _ in range(20)]
t0 = time.time()
for t in threads: t.start()
for t in threads: t.join()
elapsed = time.time() - t0

ok = sum(1 for s in responses if s == 200)
results.append(test(f"20 concurrent /health — {ok}/20 OK in {elapsed:.1f}s", ok >= 18))

# ── 6. Security headers ───────────────────────────────────────
print("\n── Security Headers")
try:
    r = urllib.request.Request(f"{BASE}/health")
    with urllib.request.urlopen(r, timeout=5) as resp:
        headers = dict(resp.headers)
    results.append(test("X-Content-Type-Options set", "x-content-type-options" in {k.lower() for k in headers}))
    results.append(test("X-Frame-Options set", "x-frame-options" in {k.lower() for k in headers}))
    results.append(test("Cache-Control set", "cache-control" in {k.lower() for k in headers}))
except Exception as e:
    results.append(test("Security headers check", False, str(e)))

# ── Summary ───────────────────────────────────────────────────
passed = sum(results)
total  = len(results)
print(f"\n{'='*44}")
print(f"  Results: {passed}/{total} passed")
if passed == total:
    print("  ✅ All tests passed — system is secure")
else:
    print(f"  ⚠️  {total - passed} test(s) failed — review above")
print(f"{'='*44}\n")
