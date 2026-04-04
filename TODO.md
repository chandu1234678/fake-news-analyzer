# FactChecker AI — Improvement To-Do List

## UI / UX (Extension)

- [x] 1. Make verdict dominate the fact card (28px bold, hero layout)
- [x] 2. Login page — add logo, tighten header, update tagline
- [x] 3. Content script — floating "TruthScan this" tooltip on text selection
- [x] 4. Fact card — "Analyzed from X sources · Bias checked · ML + AI + News" meta line
- [x] 5. Loading state — replace typing dots with "Analyzing claim... Checking sources... Computing verdict..."
- [x] 6. Empty state — add "or analyze this page" button that extracts page text
- [x] 7. Source credibility tags — HIGH / MED badge next to each source based on domain

## Backend / ML

- [x] 8. PostgreSQL migration — persistent DB on Render
- [x] 9. Production connection pooling in database.py
- [x] 10. Retrain ML model on 98k samples (90% accuracy, bigrams, 50k features)
- [x] 11. Replace heuristic AI scoring — make LLM return structured JSON verdict
- [x] 12. Evidence stance scoring — classify each source as support / contradict / neutral
- [x] 13. Meta-decision model — train a small model on ML + AI + evidence scores instead of fixed weights
- [ ] 14. Confidence calibration — add temperature scaling, plot reliability curve
- [x] 15. Uncertainty output — return "Insufficient evidence" when confidence is low and sources conflict
- [ ] 16. Ablation study — measure F1 with/without each pipeline component

## Architecture / Robustness

- [ ] 17. Data quality filter — deduplicate, min length, source blacklist before training
- [ ] 18. Drift detection — track prediction distribution, trigger retraining on shift
- [ ] 19. Adversarial test set — paraphrased claims, partial truths, misleading headlines
- [ ] 20. Failure detection layer — system abstains when evidence is too weak

## Deploy / Infra

- [x] 21. render.yaml — remove hardcoded SQLite DATABASE_URL, add Brevo env vars
- [x] 22. Email — switch to Brevo HTTP API (SMTP blocked on Render)
- [ ] 23. UptimeRobot — set up 5-min ping to keep Render free tier awake
- [ ] 24. Commit and push all current changes

## Research / Differentiation

- [ ] 25. Evidence consistency score — support vs contradict ratio across sources
- [ ] 26. Source credibility graph — score domains by historical reliability
- [ ] 27. Temporal tracking — store how a claim's verdict changes over time
- [ ] 28. Contradiction meter in UI — visual indicator when sources disagree
