# Fake News Analyzer – Chrome Extension

This project is a browser extension that analyzes selected news content and estimates whether the information may be misleading or false.

The extension connects to a FastAPI backend which performs machine learning prediction and AI-based reasoning.

## Objective

The main goal of this project is to design a structured fact-checking pipeline that includes:

- Claim detection
- ML-based probability estimation
- LLM-generated reasoning
- Confidence score calculation

The focus was not only on prediction accuracy but also on system design.

## Features

- Right-click news analysis from browser
- Sends selected text to backend API
- ML-based probability score
- LLM explanation output
- Combined confidence score
- Backend deployed on Render

## System Flow

1. User selects text in browser
2. Extension sends text to backend `/analyze`
3. Backend performs:
   - Claim detection
   - ML classification using TF-IDF + sklearn
   - LLM reasoning through API
4. Scores are combined
5. Structured result is returned

## Technical Design

The backend is structured into:

- API routes
- ML model loader
- LLM integration service
- Score aggregation logic

Claim detection was added to prevent non-factual text from being analyzed incorrectly.

## Tech Stack

Frontend:
- JavaScript
- Chrome Extension (Manifest V3)

Backend:
- FastAPI
- Scikit-learn
- TF-IDF vectorizer
- LLM API integration
- Render deployment

## Key Learnings

- Browser extension architecture
- API communication between frontend and backend
- Combining ML and LLM systems
- Handling noisy real-world text input
- Deployment challenges in free-tier hosting

## Future Improvements

- Improved claim classification
- Database-based history tracking
- User authentication system
- Performance optimization
images:
<img width="1365" height="684" alt="image" src="https://github.com/user-attachments/assets/c7e3b2f6-910d-4616-8ffd-65378737d900" />
<img width="1360" height="649" alt="image" src="https://github.com/user-attachments/assets/e1f78c70-62b0-4405-9f99-dbe16ffe2cda" />
This extension communicates with the backend available at:
https://github.com/chandu1234678/fake-news-backend
