Fake News Analyzer – Chrome Extension

This project is a browser extension that analyzes selected news content and estimates whether the information may be misleading or false.

It connects to a FastAPI backend that combines machine learning and AI reasoning.

Objective

To build a multi-stage fact-checking system that:

Detects whether text is a factual claim

Estimates probability using an ML model

Generates reasoning using an LLM

Produces a structured confidence score

Features

Right-click news analysis

ML-based probability scoring

LLM explanation generation

Structured verdict output

Backend deployment on Render

System Flow

User selects text

Extension sends request to backend /analyze

Backend performs:

Claim detection

ML prediction

LLM reasoning

Final confidence score is generated

Result is returned to extension

Tech Stack

Frontend:

JavaScript

Chrome Extension (Manifest V3)

Backend:

FastAPI

Scikit-learn

TF-IDF vectorizer

LLM API integration

What I Learned

Browser extension architecture

Combining ML and LLM systems

Handling noisy real-world inputs

Backend deployment challenges
images:
<img width="1365" height="684" alt="image" src="https://github.com/user-attachments/assets/c7e3b2f6-910d-4616-8ffd-65378737d900" />
<img width="1360" height="649" alt="image" src="https://github.com/user-attachments/assets/e1f78c70-62b0-4405-9f99-dbe16ffe2cda" />

