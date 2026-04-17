# Phase 4: Production Hardening - Implementation Plan

## Current Status Overview

### ✅ Completed (60%)
- [x] P4.2.1 - Uncertainty sampling (0.45-0.55 confidence)
- [x] P4.2.3 - UserFeedback table for corrections
- [x] P4.2.4 - Weekly retraining pipeline (`retrain_from_feedback.py`)
- [x] P4.2.5 - Active learning metrics tracking
- [x] P4.4.2 - Model versioning (`model_version.json`)

### ⏳ Pending (40%)
- [ ] P4.1 - SHAP Explainability (5 tasks)
- [ ] P4.2.2 - Review queue UI for uncertain claims
- [ ] P4.3 - A/B Testing Framework (4 tasks)
- [ ] P4.4 - Deployment & Monitoring (4 tasks)

---

## Priority Implementation Order

### 🔥 Priority 1: SHAP Explainability (P4.1)
**Impact**: High - Improves user trust and transparency  
**Effort**: Medium - Well-documented spec exists  
**Timeline**: 1-2 weeks

#### Tasks:
1. **P4.1.1 - Integrate SHAP for TF-IDF Model** (2-3 days)
   - Install `shap` library
   - Create `SHAPExplainer` class for TF-IDF model
   - Implement `KernelExplainer` with background data
   - Add caching for explainer instances

2. **P4.1.2 - Extract Attention Weights from DeBERTa** (2-3 days)
   - Create `AttentionExtractor` class
   - Hook into transformer attention layers
   - Aggregate multi-head attention
   - Compute token-level importance

3. **P4.1.3 - Generate SHAP-based Highlights** (1-2 days)
   - Replace heuristic `highlight.py` logic
   - Implement `generate_shap_highlights()` function
   - Merge adjacent tokens into phrases
   - Map to character positions

4. **P4.1.4 - API Integration** (1 day)
   - Add `/explain` endpoint
   - Integrate SHAP into `/message` pipeline
   - Add fallback to heuristic highlighting
   - Update response schemas

5. **P4.1.5 - UI Visualization** (1-2 days)
   - Create SHAP explanation card component
   - Color-code highlights by direction
   - Add tooltips with explanations
   - Test across different claim types

**Deliverables**:
- `backend/app/analysis/shap_explainer.py`
- `backend/app/analysis/attention_extractor.py`
- Updated `backend/app/analysis/highlight.py`
- New `/explain` endpoint
- Updated extension UI components

---

### 🎯 Priority 2: Review Queue UI (P4.2.2)
**Impact**: Medium - Enables active learning workflow  
**Effort**: Low - Simple CRUD UI  
**Timeline**: 2-3 days

#### Tasks:
1. **Backend API** (1 day)
   - Add `/review/queue` endpoint (get uncertain claims)
   - Add `/review/submit` endpoint (submit corrections)
   - Filter claims by confidence range (0.45-0.55)
   - Pagination support

2. **Extension UI** (1-2 days)
   - Create `review.html` page
   - Display uncertain claims in queue
   - Add correction form (fake/real/uncertain)
   - Show review statistics

**Deliverables**:
- `backend/app/routes/review_routes.py`
- `extension/popup/review.html`
- `extension/popup/review.js`

---

### 📊 Priority 3: A/B Testing Framework (P4.3)
**Impact**: High - Enables data-driven improvements  
**Effort**: Medium - Requires careful design  
**Timeline**: 1 week

#### Tasks:
1. **P4.3.1 - A/B Test Infrastructure** (2 days)
   - Create `ABTest` model (test_id, variant, user_id)
   - Add `/ab/assign` endpoint (assign user to variant)
   - Implement consistent hashing for assignment
   - Add feature flags for test control

2. **P4.3.2 - Metrics Tracking** (2 days)
   - Track accuracy per variant
   - Track latency per variant
   - Track user trust (feedback rate)
   - Track sharing reduction (friction bypass rate)

3. **P4.3.3 - Analysis Dashboard** (2 days)
   - Create `/ab/results` endpoint
   - Display variant performance comparison
   - Statistical significance testing
   - Champion/challenger recommendation

4. **P4.3.4 - Extension Integration** (1 day)
   - Fetch variant assignment on load
   - Route to appropriate model version
   - Track variant in analytics events

**Deliverables**:
- `backend/app/models.py` (ABTest model)
- `backend/app/routes/ab_routes.py`
- `extension/popup/ab_test.js`
- A/B test dashboard UI

---

### 🚀 Priority 4: Deployment & Monitoring (P4.4)
**Impact**: High - Production reliability  
**Effort**: High - Infrastructure work  
**Timeline**: 2 weeks

#### Tasks:
1. **P4.4.1 - HuggingFace Spaces Deployment** (2-3 days)
   - Create Spaces app for transformer inference
   - Add API endpoint wrapper
   - Configure auto-scaling
   - Test latency and throughput

2. **P4.4.3 - Prometheus Metrics** (2-3 days)
   - Install `prometheus-client`
   - Add custom metrics (accuracy, latency, cache hit rate)
   - Expose `/metrics` endpoint
   - Configure Prometheus scraping

3. **P4.4.4 - Grafana Dashboard** (2-3 days)
   - Setup Grafana instance
   - Create dashboards for:
     - Model performance (accuracy, F1, calibration)
     - System health (latency, throughput, errors)
     - User metrics (requests, feedback, corrections)
   - Add alerting rules

4. **P4.4.5 - Canary Deployment** (2-3 days)
   - Implement model versioning in API
   - Add traffic splitting (90% stable, 10% canary)
   - Automated rollback on error rate spike
   - Gradual rollout strategy

**Deliverables**:
- HuggingFace Spaces deployment
- Prometheus metrics integration
- Grafana dashboards
- Canary deployment pipeline

---

## Implementation Approach

### Week 1-2: SHAP Explainability
**Goal**: Replace heuristic highlighting with SHAP-based explanations

**Day 1-2**: SHAP for TF-IDF
- Install dependencies
- Implement `SHAPExplainer` class
- Test with existing model
- Add caching

**Day 3-4**: Attention Extraction
- Implement `AttentionExtractor`
- Test with DeBERTa model
- Aggregate attention weights
- Normalize scores

**Day 5-6**: Highlight Generation
- Update `highlight.py`
- Implement phrase merging
- Map to character positions
- Test with various claims

**Day 7-8**: API & UI Integration
- Add `/explain` endpoint
- Update `/message` pipeline
- Create SHAP card UI
- End-to-end testing

**Day 9-10**: Polish & Documentation
- Performance optimization
- Error handling
- Documentation
- User testing

### Week 3: Review Queue + A/B Testing Setup
**Goal**: Enable active learning and experimentation

**Day 1-2**: Review Queue
- Backend API endpoints
- Extension UI pages
- Integration testing

**Day 3-5**: A/B Testing Infrastructure
- Database models
- Assignment logic
- Metrics tracking
- Basic dashboard

### Week 4-5: Monitoring & Deployment
**Goal**: Production-grade observability

**Day 1-3**: Prometheus + Grafana
- Metrics instrumentation
- Dashboard creation
- Alert configuration

**Day 4-5**: HuggingFace Spaces
- Model deployment
- API wrapper
- Load testing

---

## Technical Specifications

### SHAP Explainer API

```python
# Request
POST /explain
{
  "text": "COVID vaccines contain microchips",
  "model_type": "auto",  # "tfidf" | "transformer" | "auto"
  "include_attention": true,
  "num_samples": 100
}

# Response
{
  "text": "COVID vaccines contain microchips",
  "prediction": {
    "verdict": "fake",
    "confidence": 0.94,
    "fake_probability": 0.94
  },
  "shap_explanation": {
    "base_value": 0.5,
    "token_importances": [
      {"token": "microchips", "importance": 0.35, "direction": "fake", "confidence": 0.92},
      {"token": "vaccines", "importance": 0.12, "direction": "fake", "confidence": 0.65}
    ],
    "top_positive": [...],  # Top 5 fake signals
    "top_negative": [...]   # Top 5 real signals
  },
  "attention_weights": {
    "tokens": ["COVID", "vaccines", "contain", "microchips"],
    "aggregated_scores": [0.15, 0.25, 0.10, 0.50]
  },
  "highlights": [
    {
      "phrase": "microchips",
      "importance": 0.35,
      "direction": "fake",
      "position": {"start": 25, "end": 35},
      "confidence": 0.92,
      "explanation": "This word strongly indicates misinformation"
    }
  ],
  "latency_ms": 245
}
```

### Review Queue API

```python
# Get uncertain claims
GET /review/queue?limit=10&offset=0

# Response
{
  "claims": [
    {
      "id": "claim_123",
      "text": "...",
      "verdict": "uncertain",
      "confidence": 0.48,
      "created_at": "2026-04-17T10:30:00Z"
    }
  ],
  "total": 156,
  "page": 1
}

# Submit correction
POST /review/submit
{
  "claim_id": "claim_123",
  "corrected_verdict": "fake",
  "reason": "Verified with multiple sources"
}
```

### A/B Test API

```python
# Assign variant
GET /ab/assign?user_id=user_123&test_id=model_v2_test

# Response
{
  "test_id": "model_v2_test",
  "variant": "B",  # "A" (control) or "B" (treatment)
  "model_version": "2.1.0"
}

# Track metric
POST /ab/track
{
  "test_id": "model_v2_test",
  "variant": "B",
  "metric": "accuracy",
  "value": 0.96
}
```

---

## Success Criteria

### SHAP Explainability
- [ ] SHAP computation completes in <500ms for typical claims
- [ ] Highlights match user intuition in 80%+ of cases
- [ ] Fallback to heuristic highlighting works seamlessly
- [ ] UI displays explanations clearly and intuitively
- [ ] User trust increases (measured via feedback)

### Review Queue
- [ ] Uncertain claims (0.45-0.55) are surfaced correctly
- [ ] Corrections are stored and used for retraining
- [ ] UI is intuitive and easy to use
- [ ] Review throughput: 10+ corrections per day

### A/B Testing
- [ ] Variant assignment is consistent per user
- [ ] Metrics are tracked accurately
- [ ] Statistical significance is calculated correctly
- [ ] Dashboard shows clear performance comparison
- [ ] Can run 2+ concurrent tests

### Monitoring
- [ ] Prometheus metrics are exposed and scraped
- [ ] Grafana dashboards show real-time data
- [ ] Alerts trigger on anomalies
- [ ] Canary deployment works without downtime
- [ ] 99.9% uptime maintained

---

## Risk Mitigation

### SHAP Performance Risk
**Risk**: SHAP computation too slow for production  
**Mitigation**:
- Use caching aggressively
- Reduce num_samples for faster computation
- Implement timeout with fallback
- Consider pre-computing for common claims

### Model Deployment Risk
**Risk**: HuggingFace Spaces has downtime  
**Mitigation**:
- Keep local model as fallback
- Implement retry logic
- Monitor uptime closely
- Have backup deployment ready

### A/B Test Validity Risk
**Risk**: Sample size too small for significance  
**Mitigation**:
- Calculate required sample size upfront
- Run tests for minimum duration (1 week)
- Use Bayesian A/B testing for faster results
- Monitor for Simpson's paradox

---

## Next Steps

1. **Review this plan** - Confirm priorities and timeline
2. **Setup development environment** - Install SHAP, configure tools
3. **Start with P4.1.1** - SHAP for TF-IDF model
4. **Iterate and test** - Build incrementally, test thoroughly
5. **Deploy and monitor** - Roll out gradually, watch metrics

**Ready to start implementation?** Let me know which task you'd like to tackle first!
