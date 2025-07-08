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
