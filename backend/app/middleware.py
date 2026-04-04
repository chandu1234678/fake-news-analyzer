"""
Security middleware — rate limiting, headers, request size guard.
All in one place so main.py stays clean.
"""
import time
import logging
from collections import defaultdict
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ── Rate limit config per route prefix ───────────────────────
# (requests, window_seconds)
_LIMITS = {
    "/auth/login":           (10,  60),   # 10 per min — brute force guard
    "/auth/signup":          (5,   60),   # 5 per min
    "/auth/forgot-password": (5,  300),   # 5 per 5 min — OTP abuse guard
    "/auth/reset-password":  (10,  60),
    "/auth/google":          (10,  60),
    "/message":              (30,  60),   # 30 per min per IP
    "/feedback":             (20,  60),
    "/stats":                (30,  60),
    "/credibility":          (20,  60),
    "/history":              (60,  60),   # generous for history reads
}
_DEFAULT_LIMIT = (60, 60)  # fallback: 60 req/min

_store: dict = defaultdict(list)

MAX_BODY_BYTES = 64 * 1024  # 64 KB max request body


def _get_limit(path: str):
    for prefix, limit in _LIMITS.items():
        if path.startswith(prefix):
            return limit
    return _DEFAULT_LIMIT


def _client_key(request: Request, path: str) -> str:
    # Use forwarded IP (Render puts real IP in X-Forwarded-For)
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.client.host
    return f"{ip}:{path}"


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # ── Skip health checks ────────────────────────────────
        if path == "/health":
            return await call_next(request)

        # ── Request body size guard ───────────────────────────
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large (max 64KB)"}
            )

        # ── Rate limiting ─────────────────────────────────────
        max_req, window = _get_limit(path)
        key = _client_key(request, path)
        now = time.time()
        window_start = now - window
        _store[key] = [t for t in _store[key] if t > window_start]

        if len(_store[key]) >= max_req:
            logger.warning("Rate limit hit: %s on %s", key, path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": str(window)},
            )
        _store[key].append(now)

        # ── Process request ───────────────────────────────────
        response: Response = await call_next(request)

        # ── Security headers ──────────────────────────────────
        response.headers["X-Content-Type-Options"]    = "nosniff"
        response.headers["X-Frame-Options"]           = "DENY"
        response.headers["X-XSS-Protection"]          = "1; mode=block"
        response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"]        = "geolocation=(), microphone=(), camera=()"
        response.headers["Cache-Control"]             = "no-store"

        return response
