from fastapi import APIRouter
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.analysis.ml import run_ml_analysis
from app.analysis.ai import run_ai_analysis
from app.analysis.explain import explain
from app.analysis.evidence import fetch_evidence
from app.logic.decision import decide

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    ml = run_ml_analysis(req.text)

    raw_ai_score, explanation = run_ai_analysis(req.text)
    ai_score = float(raw_ai_score) if raw_ai_score is not None else 0.0

    evidence_score, evidence_sources = fetch_evidence(req.text)

    verdict, confidence = decide(
        ml_fake=ml["fake"],
        ai_fake=ai_score,
        evidence_score=evidence_score,
    )

    return {
        "verdict": verdict,
        "confidence": confidence,
        "ml_score": ml["fake"],
        "ai_score": ai_score,
        "keywords": explain(req.text),
        "explanation": explanation,
        "evidence": evidence_sources or ["No verified sources found"],
    }
