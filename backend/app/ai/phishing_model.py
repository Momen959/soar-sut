"""ML-backed phishing detection with heuristic fallback."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from spellchecker import SpellChecker


SUSPICIOUS_KEYWORDS = {
    "prize",
    "winner",
    "offer",
    "urgent",
    "password",
    "bank",
    "verify",
    "account",
    "alert",
    "click",
}


class HeuristicDetector:
    """Simple, explainable scoring for phishing emails."""

    def __init__(self, spelling_threshold: float = 0.18, keyword_weight: float = 0.4):
        self.spellchecker = SpellChecker()
        self.spelling_threshold = spelling_threshold
        self.keyword_weight = keyword_weight

    @staticmethod
    def _tokenise(text: str) -> List[str]:
        return re.findall(r"[a-zA-Z']+", text.lower())

    def _spelling_score(self, tokens: Iterable[str]) -> float:
        tokens = list(tokens)
        if not tokens:
            return 0.0
        misspelled = self.spellchecker.unknown(tokens)
        return len(misspelled) / len(tokens)

    def _keyword_score(self, tokens: Iterable[str]) -> float:
        tokens = list(tokens)
        if not tokens:
            return 0.0
        matches = sum(1 for token in tokens if token in SUSPICIOUS_KEYWORDS)
        return matches / len(tokens)

    def analyse(self, subject: str, body: str) -> Dict[str, float | str]:
        tokens = self._tokenise(f"{subject} {body}")
        spelling_score = self._spelling_score(tokens)
        keyword_score = self._keyword_score(tokens)

        composite_score = min(
            1.0,
            spelling_score * (1 - self.keyword_weight) + keyword_score * self.keyword_weight,
        )

        label = "suspicious" if composite_score >= self.spelling_threshold else "safe"

        return {
            "engine": "heuristic",
            "spelling_score": round(spelling_score, 3),
            "keyword_score": round(keyword_score, 3),
            "composite_score": round(composite_score, 3),
            "model_label": label,
        }


class SklearnDetector:
    """RandomForest-based phishing classifier persisted to disk."""

    def __init__(
        self,
        model_path: Path,
        vectorizer_path: Path,
        threshold: float = 0.5,
    ):
        self.model_path = model_path
        self.vectorizer_path = vectorizer_path
        self.threshold = threshold
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.model: Optional[RandomForestClassifier] = None
        self._load_artifacts()

    def _load_artifacts(self) -> None:
        if self.model_path.exists() and self.vectorizer_path.exists():
            self.model = joblib.load(self.model_path)
            self.vectorizer = joblib.load(self.vectorizer_path)
        else:
            self.model = None
            self.vectorizer = None

    def is_ready(self) -> bool:
        return self.model is not None and self.vectorizer is not None

    def analyse(self, subject: str, body: str) -> Dict[str, float | str]:
        if not self.is_ready():
            raise RuntimeError("Sklearn model is not ready; train the detector first.")

        combined_text = f"{subject} {body}".strip()
        features = self.vectorizer.transform([combined_text])
        proba = float(self.model.predict_proba(features)[0][1])
        label = "suspicious" if proba >= self.threshold else "safe"

        return {
            "engine": "ml",
            "probability": round(proba, 3),
            "composite_score": round(proba, 3),
            "model_label": label,
        }

    def train(self, data_path: Path) -> Dict[str, str]:
        dataset = pd.read_csv(data_path)
        dataset["clean_text"] = dataset["Email Text"].apply(self._clean_text)
        dataset["label"] = dataset["Email Type"].map({"Phishing Email": 1, "Safe Email": 0})

        X = dataset["clean_text"]
        y = dataset["label"]

        self.vectorizer = TfidfVectorizer(max_features=5000)
        X_vect = self.vectorizer.fit_transform(X)

        X_train, X_test, y_train, y_test = train_test_split(
            X_vect, y, test_size=0.2, random_state=42
        )
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)

        report = classification_report(
            y_test, y_pred, target_names=["Safe Email", "Phishing Email"]
        )

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.vectorizer_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.vectorizer, self.vectorizer_path)

        return {"report": report}

    @staticmethod
    def _clean_text(text: str) -> str:
        text = str(text).lower()
        text = re.sub(r"http\S+", " ", text)
        text = re.sub(r"[^a-z\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text


class PhishingDetector:
    """High-level detector that prefers ML but falls back to heuristics."""

    def __init__(
        self,
        model_path: Path,
        vectorizer_path: Path,
        threshold: float = 0.5,
    ):
        self.sklearn_detector = SklearnDetector(model_path, vectorizer_path, threshold)
        self.heuristic_detector = HeuristicDetector()

    def analyse(self, subject: str, body: str) -> Dict[str, float | str]:
        if self.sklearn_detector.is_ready():
            return self.sklearn_detector.analyse(subject, body)
        return self.heuristic_detector.analyse(subject, body)

    def train(self, data_path: Path) -> Dict[str, str]:
        return self.sklearn_detector.train(data_path)

    def is_ml_ready(self) -> bool:
        return self.sklearn_detector.is_ready()


@lru_cache
def get_detector(
    model_path: str,
    vectorizer_path: str,
    threshold: float = 0.5,
) -> PhishingDetector:
    """Shared detector instance keyed by artifact locations."""

    return PhishingDetector(Path(model_path), Path(vectorizer_path), threshold)
