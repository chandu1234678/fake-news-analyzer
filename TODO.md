# FactChecker AI — Improvement To-Do List

## UI / UX (Extension)

- [x] 1. Make verdict dominate the fact card (28px bold, hero layout)
- [x] 2. Login page — add logo, tighten header, update tagline
- [x] 3. Content script — floating "TruthScan this" tooltip on text selection
- [x] 4. Fact card — "Analyzed from X sources · Bias checked · ML + AI + News" meta line
- [x] 5. Loading state — replace typing dots with "Analyzing claim... Checking sources... Computing verdict..."
- [x] 6. Empty state — add "or analyze this page" button that extracts page text
- [x] 7. Source credibility tags — HIGH / MED badge next to each source based on domain
- [x] 29. User feedback button — "Was this verdict wrong?" stores correction for future retraining
- [x] 30. Manipulation detection badge — flag emotionally charged / sensational language in the claim
- [x] 32. Claim extraction — for long inputs, split into atomic sub-claims and verify each separately
- [ ] 35. Highlighted suspicious phrases — underline/mark key phrases in the claim that triggered fake signals
- [ ] 36. Contradiction detail — expand stance meter to show which sources support vs contradict

## Backend / ML

- [x] 8. PostgreSQL migration — persistent DB on Render
- [x] 9. Production connection pooling in database.py
- [x] 10. Retrain ML model on 98k samples (90% accuracy, bigrams, 50k features)
- [x] 11. Replace heuristic AI scoring — make LLM return structured JSON verdict
- [x] 12. Evidence stance scoring — classify each source as support / contradict / neutral
- [x] 13. Meta-decision model — train a small model on ML + AI + evidence scores instead of fixed weights
- [x] 14. Confidence calibration — isotonic regression via CalibratedClassifierCV
- [x] 15. Uncertainty output — return "Insufficient evidence" when confidence is low and sources conflict
- [x] 16. Ablation study — measure F1 with/without each pipeline component
- [x] 31. Manipulation / bias detection — score emotional language, clickbait patterns in claim text
- [x] 32. Claim extraction — for long inputs, split into atomic sub-claims and verify each separately
- [ ] 33. User feedback DB model — store predicted vs actual corrections for retraining ← model exists, need training script
- [ ] 34. Model versioning — keep v1/v2/v3 joblib files, log which version served each prediction
- [ ] 37. Data quality filter — deduplicate, min length, source blacklist before training (partially done in train.py)
- [ ] 38. Drift detection — track prediction distribution, alert when shift detected
- [ ] 39. Calibration curve — plot reliability diagram, add isotonic regression to ML model
- [ ] 40. Adversarial test set — paraphrased claims, partial truths, misleading headlines
- [ ] 41. Source credibility dynamic scoring — learn trust scores from feedback, not just static map
- [ ] 42. Temporal claim tracking — store how a claim's verdict changes over time across requests

## Deploy / Infra

- [x] 21. render.yaml — remove hardcoded SQLite DATABASE_URL, add Brevo env vars
- [x] 22. Email — switch to Brevo HTTP API (SMTP blocked on Render)
- [ ] 23. UptimeRobot / cron-job.org — set up 5-min ping to keep Render free tier awake
- [x] 24. Commit and push all current changes

## Research / Differentiation

- [x] 25. Evidence consistency score — support vs contradict ratio across sources
- [ ] 26. Source credibility graph — dynamic domain trust scoring (static map done, learning pending)
- [ ] 27. Temporal tracking — store how a claim's verdict changes over time
- [x] 28. Contradiction meter in UI — visual indicator when sources disagree

## Next Priority (implement in order)

- [ ] A. Calibration curve + isotonic regression on ML model (proves rigor)
- [ ] B. Adversarial test set generation (LLM paraphrases, partial truths)
- [ ] C. Feedback → retraining pipeline (use UserFeedback table as labeled data)
- [ ] D. Model versioning (save with timestamp, log version in health endpoint)
- [ ] E. Drift detection (track daily prediction distribution, alert on shift)
- [ ] F. Highlighted suspicious phrases in UI
