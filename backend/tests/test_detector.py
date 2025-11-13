"""Basic smoke tests for the phishing detector."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.ai.phishing_model import PhishingDetector


def _build_detector() -> PhishingDetector:
    return PhishingDetector(
        model_path=Path("/tmp/nonexistent_model.joblib"),
        vectorizer_path=Path("/tmp/nonexistent_vectorizer.joblib"),
    )


def test_suspicious_email_flagged():
    detector = _build_detector()
    result = detector.analyse("Urgent: Verify your account", "Click here to claim your prize")

    assert result["model_label"] == "suspicious"
    assert result["composite_score"] >= 0


def test_calm_email_marked_safe():
    detector = _build_detector()
    result = detector.analyse("Weekly meeting", "Looking forward to our sync tomorrow.")

    assert result["model_label"] == "safe"



