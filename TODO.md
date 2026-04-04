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
- [ ] 30. Manipulation detection badge — flag emotionally charged / sensational language in the claim

## Backend / ML

- [x] 8. PostgreSQL migration — persistent DB on Render
- [x] 9. Production connection pooling in database.py
- [x] 10. Retrain ML model on 98k samples (90% accuracy, bigrams, 50k features)
- [x] 11. Replace heuristic AI scoring — make LLM return structured JSON verdict
- [x] 12. Evidence stance scoring — classify each source as support / contradict / neutral
- [x] 13. Meta-decision model — train a small model on ML + AI + evidence scores instead of fixed weights
- [x] 14. Confidence calibration — isotonic regression via CalibratedClassifierCV (done in item 13)
- [x] 15. Uncertainty output — return "Insufficient evidence" when confidence is low and sources conflict
- [x] 16. Ablation study — measure F1 with/without each pipeline component
- [x] 31. Manipulation / bias detection — score emotional language, clickbait patterns in claim text
- [ ] 32. Claim extraction — for long inputs, split into atomic sub-claims and verify each separately

## Architecture / Robustness

- [ ] 17. Data quality filter — deduplicate, min length, source blacklist before training
- [ ] 18. Drift detection — track prediction distribution, trigger retraining on shift
- [ ] 19. Adversarial test set — paraphrased claims, partial truths, misleading headlines
- [ ] 20. Failure detection layer — system abstains when evidence is too weak (partially done via item 15)
- [ ] 33. User feedback DB model — store predicted vs actual corrections for retraining
- [ ] 34. Model versioning — keep v1/v2/v3 joblib files, log which version served each prediction

## Deploy / Infra

- [x] 21. render.yaml — remove hardcoded SQLite DATABASE_URL, add Brevo env vars
- [x] 22. Email — switch to Brevo HTTP API (SMTP blocked on Render)
- [ ] 23. UptimeRobot — set up 5-min ping to keep Render free tier awake
- [x] 24. Commit and push all current changes

## Research / Differentiation

- [x] 25. Evidence consistency score — support vs contradict ratio across sources (done in item 12)
- [ ] 26. Source credibility graph — dynamic domain trust scoring (static map done, learning pending)
- [ ] 27. Temporal tracking — store how a claim's verdict changes over time
- [x] 28. Contradiction meter in UI — visual indicator when sources disagree (done in item 12)
