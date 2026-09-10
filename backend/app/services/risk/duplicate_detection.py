"""
backend/app/services/risk/duplicate_detection.py
=============================================================================
Duplicate & Highly Similar Project Description Detector for MPLADS.
=============================================================================

Identifies potentially redundant or duplicated project descriptions using text
embeddings and cosine similarity.

Architecture:
- Preferred: Sentence-Transformers (`all-MiniLM-L6-v2`) with lazy model loading.
- Resilient Fallback: Sublinear TF-IDF character/word n-gram vectorizer if the
  neural embedding model is unavailable or offline.
- Caching: In-memory hash-indexed embedding cache to avoid recalculating unchanged texts.
- Normalization: Lowercasing, whitespace stripping, punctuation filtering, and
  common public-works boilerplate removal.
- Ethical Explainability: Flags 'Potential duplicate' or 'Highly similar project description';
  never makes fraudulent accusations.
"""

import re
import logging
import hashlib
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from app.models.project import Project
    from app.services.risk.base import BaseRiskDetector, RiskDetectorResult, score_to_severity
except ImportError:
    from backend.app.models.project import Project
    from backend.app.services.risk.base import BaseRiskDetector, RiskDetectorResult, score_to_severity

logger = logging.getLogger(__name__)

# Common boilerplate prefixes/phrases in MPLADS developmental descriptions
BOILERPLATE_PATTERNS = [
    r"\bconstruction of\b",
    r"\binstallation of\b",
    r"\bprovision of\b",
    r"\brenovation of\b",
    r"\bdevelopment of\b",
    r"\bwork of\b",
    r"\bunder mplads\b",
    r"\bmplads scheme\b",
    r"\bimprovement of\b",
    r"\bsupply and installation of\b",
]


import os

class DuplicateDetector(BaseRiskDetector):
    """
    Detects semantic duplicates and near-identical project proposals.
    """
    name: str = "duplicate_detection"
    version: str = "1.0.0"

    # Class-level cache: project_id -> (text_hash, embedding_vector)
    _EMBEDDING_CACHE: Dict[str, Tuple[str, np.ndarray]] = {}
    _SENTENCE_MODEL = None
    _MODEL_INITIALIZATION_ATTEMPTED = False
    _USE_FALLBACK_TFIDF = False

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        use_neural: Optional[bool] = None
    ):
        self.model_name = model_name
        if use_neural is not None:
            self.use_neural = use_neural
        else:
            # Default to False unless explicitly set or environment variable is enabled
            # Prevents blocking network downloads during automated tests / offline runs
            self.use_neural = os.getenv("MPLADS_USE_NEURAL_DUPLICATE", "false").lower() in ("true", "1")

    def detect(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> RiskDetectorResult:
        """
        Executes duplicate detection for a given project against all other projects.
        """
        try:
            # Allow context to override neural vs tfidf if desired
            if context and "use_neural" in context:
                self.use_neural = bool(context["use_neural"])

            # 1. Fetch target project
            target = db.execute(
                select(Project).where(Project.project_id == project_id)
            ).scalar_one_or_none()

            if not target:
                return RiskDetectorResult(
                    score=0,
                    reason=f"Project '{project_id}' not found in database.",
                    severity="low",
                    details={"error": "not_found", "project_id": project_id}
                )

            # Combine title and description for comprehensive semantic comparison
            target_raw = f"{target.project_title or ''} {target.project_description or ''}".strip()
            target_clean = self._normalize_text(target_raw)

            # Handle empty / very short descriptions (<15 chars)
            if len(target_clean) < 15:
                return RiskDetectorResult(
                    score=0,
                    reason="Project description is empty or too short for reliable duplicate detection.",
                    severity="low",
                    details={
                        "raw_length": len(target_raw),
                        "cleaned_length": len(target_clean),
                        "project_id": project_id
                    }
                )

            # 2. Fetch all other candidate projects from database
            candidates = db.execute(
                select(Project.project_id, Project.project_title, Project.project_description)
                .where(Project.project_id != project_id)
            ).all()

            if not candidates:
                return RiskDetectorResult(
                    score=0,
                    reason="Insufficient project corpus in database to perform duplicate comparison.",
                    severity="low",
                    details={"candidate_count": 0, "project_id": project_id}
                )

            # Filter valid candidate texts
            valid_candidates: List[Tuple[str, str, str]] = []
            for c_id, c_title, c_desc in candidates:
                cand_raw = f"{c_title or ''} {c_desc or ''}".strip()
                cand_clean = self._normalize_text(cand_raw)
                if len(cand_clean) >= 15:
                    valid_candidates.append((c_id, c_title, cand_clean))

            if not valid_candidates:
                return RiskDetectorResult(
                    score=0,
                    reason="No other projects with sufficient description text found for comparison.",
                    severity="low",
                    details={"candidate_count": 0, "project_id": project_id}
                )

            # 3. Compute Embeddings and Cosine Similarities
            max_sim, best_match_id, best_match_title, method_used = self._find_max_similarity(
                target_id=project_id,
                target_text=target_clean,
                candidates=valid_candidates
            )

            # 4. Map similarity score to 0-100 risk score
            # S >= 0.92: Very high duplicate likelihood (85-100)
            # 0.80 <= S < 0.92: Moderate duplicate likelihood (50-84)
            # 0.65 <= S < 0.80: Low/marginal similarity (20-49)
            # S < 0.65: Negligible similarity (0-19)
            sim_pct = int(round(max_sim * 100))

            if max_sim >= 0.92:
                score = 85 + min(15, int((max_sim - 0.92) * 187.5))
                reason = (
                    f"Potential duplicate: Project description is highly similar ({sim_pct}% match) "
                    f"to project '{best_match_id}'"
                )
            elif max_sim >= 0.80:
                score = 50 + int(((max_sim - 0.80) / 0.12) * 34)
                reason = (
                    f"Project description has notable similarity ({sim_pct}% match) "
                    f"to project '{best_match_id}'"
                )
            elif max_sim >= 0.65:
                score = 20 + int(((max_sim - 0.65) / 0.15) * 29)
                reason = (
                    f"Moderate wording overlap ({sim_pct}% match) with project '{best_match_id}' "
                    "(standard sectoral template phrasing)"
                )
            else:
                score = 0
                reason = (
                    f"No duplicate or suspiciously similar project descriptions detected "
                    f"(highest match: {sim_pct}% with '{best_match_id}')"
                )

            severity = score_to_severity(score)

            return RiskDetectorResult(
                score=score,
                reason=reason,
                severity=severity,
                details={
                    "similarity": round(max_sim, 4),
                    "matched_project_id": best_match_id,
                    "matched_project_title": best_match_title,
                    "method_used": method_used,
                    "candidate_pool_size": len(valid_candidates)
                }
            )

        except Exception as e:
            logger.error("DuplicateDetector error for project %s: %s", project_id, str(e), exc_info=True)
            return RiskDetectorResult(
                score=0,
                reason=f"Unable to execute duplicate detection due to internal error: {str(e)}",
                severity="low",
                details={"error": str(e), "project_id": project_id}
            )

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        """
        Normalizes text: lowercase, remove boilerplate, strip punctuation and extra spaces.
        """
        if not text:
            return ""
        norm = text.lower()
        for bp in BOILERPLATE_PATTERNS:
            norm = re.sub(bp, " ", norm, flags=re.IGNORECASE)
        norm = re.sub(r"[^\w\s]", " ", norm)
        norm = re.sub(r"\s+", " ", norm).strip()
        return norm

    def _get_sentence_model(self):
        """
        Lazy loader for SentenceTransformer model with fallback indicator.
        """
        if not self.use_neural:
            return None

        if self._SENTENCE_MODEL is not None:
            return self._SENTENCE_MODEL

        if not self._MODEL_INITIALIZATION_ATTEMPTED:
            self._MODEL_INITIALIZATION_ATTEMPTED = True
            try:
                from sentence_transformers import SentenceTransformer
                # Try loading model (prefer local if available)
                try:
                    self.__class__._SENTENCE_MODEL = SentenceTransformer(self.model_name, local_files_only=True)
                    return self.__class__._SENTENCE_MODEL
                except Exception:
                    # If not locally cached, attempt standard load with short timeout
                    self.__class__._SENTENCE_MODEL = SentenceTransformer(self.model_name)
                    return self.__class__._SENTENCE_MODEL
            except Exception as e:
                logger.warning(
                    "SentenceTransformer unavailable ('%s'). Falling back to TF-IDF. Reason: %s",
                    self.model_name, str(e)
                )
                self.__class__._USE_FALLBACK_TFIDF = True
                return None

        return self.__class__._SENTENCE_MODEL

    def _find_max_similarity(
        self,
        target_id: str,
        target_text: str,
        candidates: List[Tuple[str, str, str]]
    ) -> Tuple[float, str, str, str]:
        """
        Calculates similarity using SentenceTransformer embeddings, or TF-IDF fallback.
        """
        if self.use_neural:
            model = self._get_sentence_model()
            if model is not None and not self._USE_FALLBACK_TFIDF:
                try:
                    return self._compute_neural_similarities(model, target_id, target_text, candidates)
                except Exception as e:
                    logger.warning("Neural embedding failed: %s. Reverting to TF-IDF.", str(e))

        # Fast, robust TF-IDF fallback
        return self._compute_tfidf_similarities(target_text, candidates)

    def _compute_neural_similarities(
        self,
        model,
        target_id: str,
        target_text: str,
        candidates: List[Tuple[str, str, str]]
    ) -> Tuple[float, str, str, str]:
        """
        Generates/retrieves neural embeddings and computes cosine similarities.
        """
        target_hash = hashlib.md5(target_text.encode("utf-8")).hexdigest()

        # Cache check for target
        if target_id in self._EMBEDDING_CACHE and self._EMBEDDING_CACHE[target_id][0] == target_hash:
            target_vec = self._EMBEDDING_CACHE[target_id][1]
        else:
            target_vec = model.encode(target_text, convert_to_numpy=True, normalize_embeddings=True)
            self._EMBEDDING_CACHE[target_id] = (target_hash, target_vec)

        best_sim = -1.0
        best_id = ""
        best_title = ""

        # Encode candidates
        texts_to_encode = []
        cand_indices = []

        for idx, (c_id, c_title, c_text) in enumerate(candidates):
            c_hash = hashlib.md5(c_text.encode("utf-8")).hexdigest()
            if c_id in self._EMBEDDING_CACHE and self._EMBEDDING_CACHE[c_id][0] == c_hash:
                cand_vec = self._EMBEDDING_CACHE[c_id][1]
                # Cosine sim with normalized vectors is just dot product
                sim = float(np.dot(target_vec, cand_vec))
                if sim > best_sim:
                    best_sim = sim
                    best_id = c_id
                    best_title = c_title
            else:
                texts_to_encode.append(c_text)
                cand_indices.append((c_id, c_title, c_hash))

        if texts_to_encode:
            cand_vecs = model.encode(texts_to_encode, convert_to_numpy=True, normalize_embeddings=True)
            for (c_id, c_title, c_hash), c_vec in zip(cand_indices, cand_vecs):
                self._EMBEDDING_CACHE[c_id] = (c_hash, c_vec)
                sim = float(np.dot(target_vec, c_vec))
                if sim > best_sim:
                    best_sim = sim
                    best_id = c_id
                    best_title = c_title

        return max(0.0, min(1.0, best_sim)), best_id, best_title, f"sentence-transformers/{self.model_name}"

    def _compute_tfidf_similarities(
        self,
        target_text: str,
        candidates: List[Tuple[str, str, str]]
    ) -> Tuple[float, str, str, str]:
        """
        Fast, robust scikit-learn TF-IDF character & word n-gram cosine similarity.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        all_texts = [target_text] + [c[2] for c in candidates]
        vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 3),
            sublinear_tf=True
        )
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        target_vec = tfidf_matrix[0:1]
        cand_vecs = tfidf_matrix[1:]

        sims = cosine_similarity(target_vec, cand_vecs)[0]
        max_idx = int(np.argmax(sims))
        best_sim = float(sims[max_idx])
        best_id = candidates[max_idx][0]
        best_title = candidates[max_idx][1]

        return max(0.0, min(1.0, best_sim)), best_id, best_title, "tfidf_ngram_fallback"
