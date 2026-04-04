# FactChecker AI — To-Do List

## UI / UX (Extension)

- [x] 1. Verdict hero layout — 28px bold, dominant verdict display
- [x] 2. Login page — logo, tightened header, tagline
- [x] 3. Content script — floating "TruthScan this" tooltip on text selection
- [x] 4. Fact card meta line — "Analyzed from X sources · Bias checked · ML + AI + News"
- [x] 5. Loading state — "Analyzing claim... Checking sources... Computing verdict..."
- [x] 6. Empty state — "Analyze this page" button extracts page text
- [x] 7. Source credibility tags — HIGH / MED / LOW badge per source
- [x] 29. User feedback button — "Was this verdict wrong?" stores correction
- [x] 30. Manipulation detection badge — flags emotionally charged / sensational language
- [x] 32. Claim extraction UI — sub-claims shown in fact card and detail page
- [x] 35. Highlighted suspicious phrases — color-coded tags in fact card and detail page
- [x] 36. Contradiction detail — stance meter shows support / neutral / conflict counts
- [x] 37. Verdict change notice — warns when same claim gets different verdict over time
- [x] 38. Dashboard — model version, drift monitor, top trusted sources, robustness score
- [x] 39. Saved page — manipulation badge and highlighted phrase tags on saved cards
- [x] 40. Detail page — flag button to report wrong verdict

## Backend / ML

- [x] 8. PostgreSQL migration — persistent DB on Render, psycopg2, pool_pre_ping
- [x] 9. Production connection pooling — database.py handles sqlite + postgres
- [x] 10. ML model retrained — 98k+ samples, bigrams, 50k features, ~90% accuracy
- [x] 11. Structured AI scoring — LLM returns JSON verdict + confidence + explanation
- [x] 12. Evidence stance scoring — support / contradict / neutral per article
- [x] 13. Meta-decision model — CalibratedClassifierCV trained on ML+AI+evidence scores
- [x] 14. Confidence calibration — isotonic regression, Brier score tracked
- [x] 15. Uncertainty output — "uncertain" when signals conflict or all near 0.5
- [x] 16. Ablation study — F1 measured with/without each pipeline component
- [x] 31. Manipulation detection — emotional language, clickbait, absolute claims scored
- [x] 32. Claim extraction — LLM splits long inputs into atomic verifiable claims
- [x] 33. User feedback model — UserFeedback table stores predicted vs actual corrections
- [x] 34. Model versioning — model_version.json saved on each train, exposed on /health
- [x] 35. Suspicious phrase highlighting — TF-IDF feature weights + pattern matching
- [x] 36. Temporal claim tracking — ClaimRecord table, verdict change detection
- [x] 41. Dynamic source credibility — trust scores per domain, weighted evidence scoring
- [x] 42. Drift detection — rolling window tracks fake rate, alerts on >20% shift
- [x] 43. Calibrated training script — train_calibrated.py with reliability curve output
- [x] 44. Adversarial test generator — gen_adversarial.py uses LLM to create paraphrases
- [x] 45. Feedback retraining pipeline — retrain_from_feedback.py with evaluation gate
- [x] 46. Data quality filter — min length 30, English check, length cap 5000, dedup in training
- [x] 47. Adversarial evaluation — eval_adversarial.py runs test set, reports F1 + robustness score
- [x] 48. Calibration curve endpoint — /stats/calibration exposes all model metrics + adversarial results
- [x] 49. /credibility endpoint — exposes dynamic trust scores

## Deploy / Infra

- [x] 21. render.yaml — updated with correct env vars
- [x] 22. Email — Brevo HTTP API, works on Render, any recipient
- [x] 24. All changes committed and pushed
- [ ] 23. UptimeRobot / cron-job.org — external ping every 5 min to keep Render alive

## Research / Differentiation

- [x] 25. Evidence consistency score — trust-weighted support vs contradict ratio
- [x] 26. Source credibility — dynamic scoring with 50+ domains, learned adjustments
- [x] 27. Temporal tracking — ClaimRecord stores every verification, detects verdict drift
- [x] 28. Contradiction meter — visual stance bar in fact card and detail page

## Next Priority

- [x] A. Dashboard upgrade — model version, drift alert, credibility stats, robustness score
- [x] B. Adversarial evaluation — eval_adversarial.py with per-type F1 breakdown
- [x] C. Calibration curve API endpoint — /stats/calibration
- [ ] D. UptimeRobot setup (manual — no code needed)
- [x] E. Saved page — manipulation/highlight badges on saved cards
