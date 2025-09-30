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

## 2025-08-09 09:30 - feat: structured AI scoring, stance evidence, meta-decision model, UI improvements (items 1-13)

## 2025-08-09 13:48 - feat: uncertainty detection, contradiction meter, source credibility tags, analyze-page button

## 2025-08-11 03:29 - feat: ablation study with F1 results, add to README

## 2025-08-12 01:42 - feat: user feedback system — store corrections in DB for retraining, inline UI

## 2025-08-12 18:56 - feat: manipulation/bias detection — sensational language, emotional amplification, urgency signals

## 2025-08-18 14:11 - feat: PostgreSQL support + Brevo email + all fixes

## 2025-08-21 07:08 - fix: popup.js duplicate explHtml, add subclaim styles, feedback styles

## 2025-08-22 05:30 - feat: calibrated ML model, adversarial test gen, feedback retraining, drift detection, model versioning

## 2025-08-24 13:58 - feat: suspicious phrase highlighting, temporal claim tracking, verdict change detection

## 2025-08-31 15:37 - feat: dynamic source credibility scoring, detail.js full upgrade with all new fields

## 2025-09-09 00:49 - docs: updated TODO with accurate completion status

## 2025-09-09 04:35 - feat: dashboard upgrade (model metrics, drift monitor, top sources), saved page badges, detail feedback button

## 2025-09-09 13:50 - feat: adversarial evaluation script, calibration+robustness API, dashboard robustness score

## 2025-09-09 14:16 - publish-ready: updated README, rate limiting on /message, manifest v2.0.0, LICENSE, history msg fix

## 2025-09-09 15:42 - fix: mark 38/39/40/46 complete, data quality filter in train.py

## 2025-09-10 07:28 - fix: 60s timeout + waking hint for Google OAuth cold start

## 2025-09-11 21:43 - perf: pre-warm Google auth token silently on login page load

## 2025-09-12 05:47 - design: Apple-style OTP email — pure white, SF Pro, minimal

## 2025-09-16 16:49 - fix: UnboundLocalError — move highlights after verdict assignment

## 2025-09-18 00:18 - feat: one-step-at-a-time loading indicator, typewriter effect on explanation and chat replies

## 2025-09-22 19:03 - security: centralized rate limiting middleware, security headers, input validation, stress test

## 2025-09-24 21:28 - test: 22/22 stress test passing — rate limiting, auth, validation, concurrent load all verified

## 2025-09-25 14:23 - feat: word-by-word typewriter on chat replies, instant on fact card explanation

## 2025-09-28 13:59 - fix: no typewriter on history load, animate only new messages

## 2025-09-29 01:55 - feat: skeleton loader, spin ring on init, markdown rendering, save feedback, no typewriter on history

## 2025-09-29 11:26 - fix: reduce ML weight for short claims, AI dominates on factual statements

## 2025-09-30 02:54 - fix: health endpoint safe drift import, revert side panel, skeleton loader, markdown rendering, save feedback
