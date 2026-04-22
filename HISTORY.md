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

## 2025-10-20 12:48 - docs: add mermaid architecture diagrams, fix project structure, improve local setup

## 2025-10-24 11:52 - feat: RoBERTa ML model (primary) + TF-IDF fallback + Colab training notebook with 5 HF datasets

## 2025-10-24 15:47 - chore: retrained models - 98.5% accuracy, brier 0.0119, 27k samples from 5 HF datasets

## 2025-10-27 18:58 - feat: industry-level hardening — security, logging, migrations, retry, pagination, indexes

## 2025-11-01 15:13 - fix: remove RoBERTa startup preload — was blocking port bind on Render free tier; add RAM guard

## 2025-11-02 20:33 - fix: revert authFetch content-type guard (breaks on proxy 503s); pin scikit-learn==1.6.1

## 2025-11-10 18:55 - feat: god-level DeBERTa fine-tuning notebook (10 datasets, ~130k samples) + configurable model via DEBERTA_MODEL env var

## 2025-11-12 22:54 - feat: Level 70+90 — cross-encoder evidence reranking + Wikidata entity verification

## 2025-11-13 22:08 - feat: real-time Brave Search API + publisher bias DB (100+ sources) + bias-weighted evidence scoring

## 2025-11-14 00:23 - feat: image+text consistency, multi-language support, cross-platform fact-check tracker

## 2025-11-14 00:40 - fix: clean DeBERTa notebook + explainability + continuous learning + stats route fix

## 2025-11-14 03:17 - feat: add verification checks to every cell in DeBERTa notebook

## 2025-11-14 06:16 - feat: attach menu (+) with image/PDF/txt support in chat input

## 2025-11-14 08:16 - fix: rewrite notebook with DistilBERT - no version issues, fp16 only on GPU, zero NaN

## 2025-11-14 16:23 - fix: remove pinned transformers version - use whatever Colab has

## 2025-11-25 23:51 - fix: pin transformers==4.41.3 + huggingface_hub==0.23.4 together - eliminates DryRunError

## 2025-11-27 22:40 - fix: remove all version pinning - use Colab's transformers 5.x as-is

## 2025-12-06 21:51 - Created using Colab

## 2025-12-14 12:48 - chore: update model_version.json - DistilBERT 98.91% accuracy

## 2025-12-19 13:16 - chore: add DEBERTA_MODEL + BRAVE_API_KEY + SERPAPI_KEY + GOOGLE_FACTCHECK_API_KEY to render.yaml and .env

## 2025-12-26 02:02 - fix: OOM - cap workers at 3, make Wikidata/platform conditional, fix req scope bug, increase body limit to 512KB

## 2025-12-26 04:13 - chore: trigger redeploy after history rewrite - repo now 4MB

## 2025-12-26 06:06 - fix: compress images to JPEG 800px before send, PDF text extraction, body limit 2MB, add .doc/.docx support

## 2025-12-26 16:13 - fix: allow image-only messages, auto-generate prompt when image sent without text

## 2026-01-11 16:53 - fix: allow send with image+no text, fix DOCX binary garbage, ensure sendText never empty

## 2026-01-14 19:03 - fix: image analysis - Gemini Vision retry with flash-lite fallback, fix rate limiting, fix error handling

## 2026-01-27 13:11 - Complete P1.1: Add all 7 training notebooks for transformer pipeline

## 2026-01-31 00:57 - Fix training pipeline: Add clean working scripts and notebook

## 2026-02-11 11:19 - Add training pipeline summary

## 2026-02-16 03:31 - Fix JSON syntax errors in all notebooks

## 2026-02-16 08:13 - Add complete training guides and transformer integration

## 2026-02-17 01:15 - Add ultimate training notebook and guides

## 2026-03-10 13:59 - Clean up completed plan files, unnecessary training files, and update .gitignore

## 2026-03-11 15:12 - Update TODO: mark cleanup task as complete

## 2026-03-11 22:20 - Update TODO: Phase 3 complete - Snorkel, multilingual, domain-specific training implemented

## 2026-03-12 07:12 - Mark UptimeRobot as complete

## 2026-03-12 14:10 - Update TODO: Mark Phase 4.2 active learning and 4.4 versioning as complete

## 2026-03-13 22:24 - Update TODO: Mark Phase 5.5 image analysis and 5.6 knowledge graph as complete

## 2026-03-17 06:08 - Add progress summary and update gitignore

## 2026-03-17 16:53 - Add comprehensive technical review document with architecture, cybersecurity, and quantum computing roadmap

## 2026-03-17 21:45 - Add executive summary with organized structure: objectives, problem statement, solution architecture, tech stack, performance metrics, and competitive analysis

## 2026-03-18 18:11 - Add Phase 4 implementation plan with priorities, timelines, and technical specs

## 2026-04-02 11:42 - Implement Phase 4.1: SHAP Explainability - Add SHAP-based token importance, attention extraction, enhanced highlighting, and /explain endpoint

## 2026-04-08 11:33 - feat: Complete Phase 4.1 - SHAP Explainability UI Visualization

## 2026-04-12 22:26 - feat: Complete Phase 4.2 - Review Queue UI for Active Learning

## 2026-04-22 12:22 - feat: Complete Phase 4.3 - A/B Testing Framework

## 2026-04-22 19:35 - feat: Complete Phase 4.4 - Monitoring & Deployment (PHASE 4 COMPLETE!)
