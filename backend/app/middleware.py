"""
Security + observability middleware.

- Rate limiting (per-IP, per-route, in-memory sliding window)
- Request body size guard
- Security headers (HSTS, X-Frame-Options, etc.)
- Request ID injection (X-Request-ID header)
- Structured request logging (method, path, status, duration, request_id)
"""
import time
import uuid
import logging
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ── Rate limit config per route prefix ───────────────────────
_LIMITS = {
    "/auth/login":           (10,  60),
    "/auth/signup":          (5,   60),
    "/auth/forgot-password": (5,  300),
    "/auth/reset-password":  (5,   60),   # tightened — brute force guard
    "/auth/google":          (10,  60),
    "/message":              (30,  60),
    "/feedback":             (20,  60),
    "/stats":                (30,  60),
    "/credibility":          (20,  60),
    "/history":              (60,  60),
}
_DEFAULT_LIMIT = (60, 60)

_store: dict = defaultdict(list)
MAX_BODY_BYTES = 2 * 1024 * 1024  # 2 MB — allows compressed image base64

# Security headers applied to every response
_SECURITY_HEADERS = {
    "X-Content-Type-Options":    "nosniff",
    "X-Frame-Options":           "DENY",
    "X-XSS-Protection":          "1; mode=block",
    "Referrer-Policy":           "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Permissions-Policy":        "geolocation=(), microphone=(), camera=()",
}


def _get_limit(path: str):
    for prefix, limit in _LIMITS.items():
        if path.startswith(prefix):
            return limit
    return _DEFAULT_LIMIT


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # ── Skip health checks ────────────────────────────────
        if path == "/health":
            response = await call_next(request)
            return response

        # ── Request body size guard ───────────────────────────
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large (max 64KB)"},
            )

        # ── Rate limiting ─────────────────────────────────────
        max_req, window = _get_limit(path)
        ip  = _client_ip(request)
        key = f"{ip}:{path}"
        now = time.time()
        _store[key] = [t for t in _store[key] if t > now - window]

        if len(_store[key]) >= max_req:
            logger.warning("rate_limit ip=%s path=%s request_id=%s", ip, path, request_id)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": str(window), "X-Request-ID": request_id},
            )
        _store[key].append(now)

        # ── Process request ───────────────────────────────────
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        # ── Structured access log ─────────────────────────────
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%s ip=%s request_id=%s",
            request.method, path, response.status_code, duration_ms, ip, request_id,
        )

        # ── Security headers ──────────────────────────────────
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        response.headers["X-Request-ID"] = request_id

        return response
