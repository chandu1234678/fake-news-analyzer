# Project Development History

This file tracks the development timeline of the Fake News Detection Extension.
Each commit represents actual work done on the project.


## 2025-05-25 11:39 - Initial commit: fake news analyzer backend + extension

## 2025-05-27 21:55 - Add gunicorn to requirements

## 2025-05-28 16:40 - Update requirements.txt

## 2025-05-28 19:11 - Sync local changes

## 2025-05-28 21:09 - changes in ai.py

## 2025-05-29 11:07 - changes in health.py

## 2025-05-29 15:41 - Refactor frontend to chat-based UI and stateless logic

## 2025-05-29 22:36 - Add README for Fake News Analyzer Chrome Extension

## 2025-05-31 21:44 - Update README formatting and content clarity

## 2025-06-02 23:11 - Add backend URL to README

## 2025-06-03 13:18 - made a new version

## 2025-06-03 13:41 - Removed the strict version pins on pandas, scikit-learn, groq, and cerebras-cloud-sdk

## 2025-06-04 12:18 - changed

## 2025-06-04 16:43 - main.py — lifespan instead of deprecated startup event ml.py — lazy load, won't crash on import evidence.py — correct .env path auth_routes.py — clean /me route decision.py — Optional type hints database.py — absolute SQLite path

## 2025-06-04 18:16 - add trained ML model artifacts

## 2025-06-05 12:42 - fix: accept HEAD requests on /health

## 2025-06-05 15:57 - fix: Kiwi OAuth fallback, HEAD health check, CSP update

## 2025-06-10 09:06 - feat: TruthScan context menu opens popup, new logo

## 2025-06-10 19:26 - feat: new square logo for all toolbar icons

## 2025-06-10 23:13 - fix: remove JWT expiry so tokens never expire + fix all nav to use chrome.runtime.getURL + remove CSP-violating inline scripts

## 2025-06-11 01:02 - fix: chrome.runtime.getURL + remove CSP-violating inline scripts

## 2025-06-11 05:30 - fix re size isuues

## 2025-06-11 07:30 - fix : Evidence weight and News bar is blue to visually distinguish it from ML (green/red) and AI (purple)

## 2025-06-12 10:47 - feat: parallel analysis pipeline, NewsAPI evidence, forgot password with OTP email

## 2025-06-12 14:21 - feat: production hardening — auth, OTP rate limiting, resend timer, deploy config

## 2025-06-14 07:25 - redesign: cleaner OTP email template matching app design system

## 2025-06-25 00:38 - RESEND_FROM was empty string in .env — or operator now falls back to default correctly Rate limit was too tight (3 per 10 min) — now 5 per 5 min Frontend now shows the 429 error clearly instead of a generic message

## 2025-06-27 00:33 - edo mail issue solve chesa anukunta

## 2025-06-28 16:55 - debug: add /auth/debug-email endpoint to diagnose Render SMTP

## 2025-07-06 00:49 - fix: revert to Resend HTTP API (SMTP blocked on Render), clear domain restriction error

## 2025-07-07 04:33 - fix: Gmail SMTP port 587 STARTTLS — works on Render, sends to any email

## 2025-07-07 23:13 - debug: TCP port test endpoint

## 2025-07-08 10:19 - fix: switch to Brevo HTTP API for OTP emails — works on Render, any recipient

## 2025-07-08 15:13 - fix: Brevo HTTP API for OTP emails — delivers to any email, verified on gitam.in

## 2025-07-09 04:16 - debug: expose email error detail on Render + config back to production

## 2025-07-13 08:42 - fix: clean error message for email failures

## 2025-07-14 04:32 - feat: PostgreSQL with production connection pooling

## 2025-07-14 18:09 - fix: remove hardcoded sqlite DATABASE_URL from render.yaml, add Brevo env vars

## 2025-07-16 23:42 - feat: retrain ML model on 98k samples (90% accuracy) with bigrams + 50k features

## 2025-07-22 13:57 - rewritten the README file

## 2025-07-24 23:10 - fix: remove CDATA wrapper from README

## 2025-08-01 22:09 - feat: replace extension icons with new logo

## 2025-08-08 19:27 - feat: replace extension icons with new logo with radme
