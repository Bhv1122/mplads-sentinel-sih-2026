"""
backend/app/services/risk/duplicate_detection_engine.py
=============================================================================
Engine 2: Duplicate Detection Engine for MPLADS Projects.
=============================================================================

Implements the common BaseRiskEngine interface contract:
{
    "engine": "duplicate_detection",
    "score": 0-100,
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "reason": "...",
    "details": {
        "matched_project_id": "...",
        "similarity": 0.0
    },
    "confidence": 0-1
}

Methodology:
1. Semantic Text Representation:
   - Combines project name (project_title) and description (project_description).
   - Normalizes text by lowercasing, whitespace stripping, punctuation cleanup,
     and public-works boilerplate removal.
2. Embedding Generation & Cosine Similarity:
   - Primary: Sentence-Transformers (all-MiniLM-L6-v2) for dense semantic vectorization.
   - Resilient Fallback: Sublinear TF-IDF character/word n-gram vectorizer for offline
     or lightweight environments.
   - Vector Dot-Product / Cosine Metric over normalized embeddings.
3. In-Memory Embedding Cache:
   - Hash-keyed embedding cache avoids redundant transformer re-encodings of unchanged projects.
4. False-Positive Reduction via Structured Information:
   - Considers location (state_id, district_name, block_name) and category (sector, sub_sector).
   - Same district / block escalates duplicate risk (high double-billing probability).
   - Different states dampen risk score (standard government phrasing across distant
     municipalities is template reuse, not project duplication).
   - Excludes self-comparison (project_id != target_project_id).
5. Configurable Thresholds:
   - Normal: similarity < threshold_possible (score 0–29, LOW)
   - Possible Duplicate: threshold_possible <= similarity < threshold_strong (score 30–59, MEDIUM)
   - Strong Duplicate: similarity >= threshold_strong (score 60–100, HIGH/CRITICAL)
"""

import os
import re
import logging
import hashlib
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from app.config import settings
    from app.models.project import Project
    from app.schemas.risk_engine import RiskLevel, EngineResult
    from app.services.risk.engine_base import BaseRiskEngine
except ImportError:
    from backend.app.config import settings
    from backend.app.models.project import Project
    from backend.app.schemas.risk_engine import RiskLevel, EngineResult
    from backend.app.services.risk.engine_base import BaseRiskEngine

logger = logging.getLogger(__name__)

# Standard boilerplate expressions common in MPLADS proposals
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
    r"\bexecution of\b",
    r"\bestablishment of\b",
    r"\bsupply of\b",
    r"\berection of\b",
    r"\bcommissioning of\b",
]


class DuplicateDetectionEngine(BaseRiskEngine):
    """
    Independent risk engine for detecting redundant, copied, or duplicate project
    proposals using semantic sentence embeddings and structured context verification.
    """
    engine_name: str = "duplicate_detection"
    version: str = "1.0.0"

    # Class-level in-memory cache: project_id -> (text_hash, embedding_vector)
    _EMBEDDING_CACHE: Dict[str, Tuple[str, np.ndarray]] = {}
    _SENTENCE_MODEL = None
    _MODEL_INITIALIZATION_ATTEMPTED = False
    _USE_FALLBACK_TFIDF = False

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        use_neural: Optional[bool] = None,
        threshold_normal: Optional[float] = None,
        threshold_possible: Optional[float] = None,
        threshold_strong: Optional[float] = None,
    ):
        """
        Initializes the duplicate detection engine with configurable thresholds.
        """
        self.model_name = model_name

        # Neural vs TF-IDF configuration
        if use_neural is not None:
            self.use_neural = use_neural
        else:
            # Check environment flag, default to True if sentence_transformers is available
            env_neural = os.getenv("MPLADS_USE_NEURAL_DUPLICATE")
            if env_neural is not None:
                self.use_neural = env_neural.lower() in ("true", "1")
            else:
                try:
                    import sentence_transformers
                    self.use_neural = True
                except ImportError:
                    self.use_neural = False

        # Configurable similarity thresholds
        cfg_thresholds = self.get_engine_thresholds()
        self.threshold_normal: float = (
            threshold_normal
            if threshold_normal is not None
            else float(cfg_thresholds.get("low", 0.60))
        )
        self.threshold_possible: float = (
            threshold_possible
            if threshold_possible is not None
            else float(cfg_thresholds.get("medium", 0.75))
        )
        self.threshold_strong: float = (
            threshold_strong
            if threshold_strong is not None
            else float(cfg_thresholds.get("high", 0.85))
        )

    # -------------------------------------------------------------------------
    # Public Evaluation Interface
    # -------------------------------------------------------------------------

    def evaluate(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> EngineResult:
        """
        Evaluates project description against candidate projects in the corpus.
        """
        try:
            # Allow runtime context overrides for neural embedding or thresholds
            if context:
                if "use_neural" in context:
                    self.use_neural = bool(context["use_neural"])
                if "threshold_normal" in context:
                    self.threshold_normal = float(context["threshold_normal"])
                if "threshold_possible" in context:
                    self.threshold_possible = float(context["threshold_possible"])
                if "threshold_strong" in context:
                    self.threshold_strong = float(context["threshold_strong"])

            # 1. Fetch target project
            stmt = select(Project).where(Project.project_id == project_id)
            target = db.execute(stmt).scalar_one_or_none()

            if not target:
                return self.build_result(
                    score=0,
                    reason=f"Project '{project_id}' not found in database.",
                    details={
                        "matched_project_id": None,
                        "similarity": 0.0,
                        "error": "not_found",
                        "project_id": project_id,
                    },
                    confidence=0.0
                )

            # 2. Extract and normalize target text
            target_text = self._combine_project_text(target)
            clean_target = self._normalize_text(target_text)

            # Handle missing or empty descriptions (< 15 meaningful characters)
            if len(clean_target) < 15:
                return self.build_result(
                    score=0,
                    reason="Project description is empty or too short for reliable duplicate detection.",
                    details={
                        "matched_project_id": None,
                        "similarity": 0.0,
                        "missing_text": True,
                        "raw_text_length": len(target_text),
                        "cleaned_text_length": len(clean_target),
                        "project_id": project_id,
                    },
                    confidence=0.0
                )

            # 3. Fetch candidate projects (strictly excluding self)
            if context and "candidates" in context:
                raw_pool = context["candidates"]
                if raw_pool and isinstance(raw_pool[0], dict):
                    valid_candidates = [c for c in raw_pool if str(c.get("project_id")) != str(project_id)]
                else:
                    valid_candidates = self.prepare_candidate_pool(raw_pool, exclude_id=project_id)
            else:
                cand_stmt = (
                    select(
                        Project.project_id,
                        Project.project_title,
                        Project.project_description,
                        Project.sector,
                        Project.sub_sector,
                        Project.state_id,
                        Project.district_name,
                        Project.block_name,
                    )
                    .where(Project.project_id != project_id)
                )
                candidate_rows = db.execute(cand_stmt).all()
                valid_candidates = self.prepare_candidate_pool(candidate_rows, exclude_id=project_id)

            if not valid_candidates:
                return self.build_result(
                    score=0,
                    reason="Insufficient project corpus in database to perform duplicate comparison.",
                    details={
                        "matched_project_id": None,
                        "similarity": 0.0,
                        "candidate_pool_size": 0,
                        "project_id": project_id,
                    },
                    confidence=0.0
                )
                return self.build_result(
                    score=0,
                    reason="No other projects with sufficient text found in corpus for duplicate comparison.",
                    details={
                        "matched_project_id": None,
                        "similarity": 0.0,
                        "candidate_pool_size": 0,
                        "project_id": project_id,
                    },
                    confidence=0.0
                )

            # 5. Compute Semantic Similarities via Embeddings
            max_sim, best_candidate, method_used, cached_flag = self._find_best_match(
                target_id=project_id,
                target_clean=clean_target,
                candidates=valid_candidates,
            )

            # 6. Structured Information & False-Positive Adjustment
            score, anomaly_type, reason, structured_info = self._compute_score_and_reason(
                target_project=target,
                matched_candidate=best_candidate,
                raw_similarity=max_sim,
            )

            # 7. Compute Confidence
            confidence = self._compute_confidence(
                target_text_len=len(clean_target),
                candidate_pool_size=len(valid_candidates),
                method_used=method_used,
                target=target,
            )

            details = {
                "matched_project_id": best_candidate["project_id"] if best_candidate else None,
                "similarity": round(max_sim, 4),
                "matched_project_title": best_candidate["project_title"] if best_candidate else None,
                "raw_similarity": round(max_sim, 4),
                "adjusted_similarity": round(structured_info.get("adjusted_similarity", max_sim), 4),
                "duplicate_classification": anomaly_type,
                "location_match": structured_info.get("location_match", "unknown"),
                "sector_match": structured_info.get("sector_match", "unknown"),
                "location_factor": structured_info.get("location_factor", 1.0),
                "sector_factor": structured_info.get("sector_factor", 1.0),
                "method_used": method_used,
                "embedding_cached": cached_flag,
                "candidate_pool_size": len(valid_candidates),
            }

            matched_id = best_candidate["project_id"] if best_candidate else None
            matched_title = best_candidate["project_title"] if best_candidate else "No matching project"
            sim_pct = round(max_sim * 100.0, 1)

            evidence_items = [
                {
                    "metric": "similarity_score",
                    "label": "Similarity Score",
                    "value": sim_pct,
                    "formatted": f"{sim_pct:.1f}%",
                },
                {
                    "metric": "matched_project_id",
                    "label": "Matched Project ID",
                    "value": str(matched_id) if matched_id else "None",
                    "formatted": str(matched_id) if matched_id else "None",
                },
                {
                    "metric": "matched_project_description",
                    "label": "Matched Project Title/Description",
                    "value": matched_title,
                    "formatted": matched_title,
                },
                {
                    "metric": "similarity_threshold",
                    "label": "Similarity Threshold",
                    "value": 75.0,
                    "formatted": ">= 75.0%",
                },
            ]

            return self.build_result(
                score=score,
                reason=reason,
                details=details,
                confidence=confidence,
                triggered=(score >= 30),
                threshold="Cosine similarity >= 75.0% (Strong duplicate) or >= 60.0% (Possible duplicate)",
                actual_value=f"{sim_pct:.1f}% semantic similarity with project '{matched_id}'" if matched_id else "No similar projects identified",
                expected_value="Independent project proposal (< 60.0% similarity)",
                reference_value=f"Matched candidate: '{matched_title}'",
                evidence=evidence_items,
                metadata=details,
            )

        except Exception as e:
            logger.error(
                "DuplicateDetectionEngine failed for project '%s': %s",
                project_id, str(e), exc_info=True
            )
            return self.build_result(
                score=0,
                reason=f"Duplicate detection encountered runtime error: {str(e)}",
                details={
                    "matched_project_id": None,
                    "similarity": 0.0,
                    "error": str(e),
                    "project_id": project_id,
                },
                confidence=0.0
            )

    # -------------------------------------------------------------------------
    # Helper: Text Preparation & Normalization
    # -------------------------------------------------------------------------

    @classmethod
    def _combine_project_text(cls, project: Project) -> str:
        """
        Combines the most informative project text fields:
        title, description, and sub_sector.
        """
        title = project.project_title or ""
        desc = project.project_description or ""
        sub_sector = project.sub_sector or ""

        # Avoid redundant concatenation if description already contains title
        if title and title.lower() in desc.lower():
            combined = desc
        else:
            combined = f"{title} {desc}".strip()

        if sub_sector and sub_sector.lower() not in combined.lower():
            combined = f"{combined} {sub_sector}".strip()

        return combined

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        """
        Normalizes text: lowercases, removes boilerplate municipal prefixes,
        strips punctuation and compresses whitespace.
        """
        if not text:
            return ""
        norm = text.lower()
        for bp in BOILERPLATE_PATTERNS:
            norm = re.sub(bp, " ", norm, flags=re.IGNORECASE)
        norm = re.sub(r"[^\w\s]", " ", norm)
        norm = re.sub(r"\s+", " ", norm).strip()
        return norm

    @classmethod
    def prepare_candidate_pool(
        cls,
        candidate_rows: List[Any],
        exclude_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Parses and pre-normalizes a list of candidate project rows or models.
        Supports model objects, SQLAlchemy tuples, and dicts.
        """
        valid: List[Dict[str, Any]] = []
        for row in candidate_rows:
            if hasattr(row, "project_id"):
                c_id = row.project_id
                c_title = row.project_title or ""
                c_desc = row.project_description or ""
                c_sector = row.sector or ""
                c_sub_sector = row.sub_sector or ""
                c_state_id = row.state_id
                c_district = getattr(row, "district_name", "") or ""
                c_block = getattr(row, "block_name", "") or ""
            elif isinstance(row, (tuple, list)):
                c_id = row[0]
                c_title = row[1] or ""
                c_desc = row[2] or ""
                c_sector = row[3] or ""
                c_sub_sector = row[4] or ""
                c_state_id = row[5]
                c_district = row[6] or ""
                c_block = row[7] or ""
            elif isinstance(row, dict):
                c_id = row.get("project_id")
                c_title = row.get("project_title") or ""
                c_desc = row.get("project_description") or ""
                c_sector = row.get("sector") or ""
                c_sub_sector = row.get("sub_sector") or ""
                c_state_id = row.get("state_id")
                c_district = row.get("district_name") or ""
                c_block = row.get("block_name") or ""
            else:
                continue

            if exclude_id and str(c_id) == str(exclude_id):
                continue

            cand_raw = f"{c_title} {c_desc}".strip()
            cand_clean = cls._normalize_text(cand_raw)
            if len(cand_clean) >= 15:
                valid.append({
                    "project_id": c_id,
                    "project_title": c_title,
                    "clean_text": cand_clean,
                    "sector": c_sector,
                    "sub_sector": c_sub_sector,
                    "state_id": c_state_id,
                    "district_name": c_district,
                    "block_name": c_block,
                })
        return valid

    # -------------------------------------------------------------------------
    # Helper: Model Loading & Embedding Computation
    # -------------------------------------------------------------------------

    def _get_sentence_model(self):
        """
        Lazy loader for SentenceTransformer with defensive fallback.
        """
        if not self.use_neural:
            return None

        if self.__class__._SENTENCE_MODEL is not None:
            return self.__class__._SENTENCE_MODEL

        if not self.__class__._MODEL_INITIALIZATION_ATTEMPTED:
            self.__class__._MODEL_INITIALIZATION_ATTEMPTED = True
            try:
                import io
                import contextlib
                from sentence_transformers import SentenceTransformer
                with contextlib.redirect_stdout(io.StringIO()):
                    try:
                        self.__class__._SENTENCE_MODEL = SentenceTransformer(
                            self.model_name, local_files_only=True
                        )
                    except Exception:
                        self.__class__._SENTENCE_MODEL = SentenceTransformer(self.model_name)
                return self.__class__._SENTENCE_MODEL
            except Exception as e:
                logger.warning(
                    "SentenceTransformer unavailable ('%s'). Falling back to TF-IDF. Error: %s",
                    self.model_name, str(e)
                )
                self.__class__._USE_FALLBACK_TFIDF = True
                return None

        return self.__class__._SENTENCE_MODEL

    def _find_best_match(
        self,
        target_id: str,
        target_clean: str,
        candidates: List[Dict[str, Any]]
    ) -> Tuple[float, Optional[Dict[str, Any]], str, bool]:
        """
        Identifies the candidate with highest cosine similarity.
        Returns (max_similarity, best_candidate_dict, method_used, was_cached).
        """
        if self.use_neural:
            model = self._get_sentence_model()
            if model is not None and not self.__class__._USE_FALLBACK_TFIDF:
                try:
                    return self._compute_neural_similarities(
                        model=model,
                        target_id=target_id,
                        target_clean=target_clean,
                        candidates=candidates,
                    )
                except Exception as e:
                    logger.warning("Neural embedding failed: %s. Using TF-IDF fallback.", str(e))

        # Resilient TF-IDF character & word n-gram fallback
        return self._compute_tfidf_similarities(target_clean, candidates)

    def _compute_neural_similarities(
        self,
        model,
        target_id: str,
        target_clean: str,
        candidates: List[Dict[str, Any]]
    ) -> Tuple[float, Optional[Dict[str, Any]], str, bool]:
        """
        Computes sentence embeddings with caching and cosine dot-product.
        """
        target_hash = hashlib.md5(target_clean.encode("utf-8")).hexdigest()
        was_cached = False

        if target_id in self._EMBEDDING_CACHE and self._EMBEDDING_CACHE[target_id][0] == target_hash:
            target_vec = self._EMBEDDING_CACHE[target_id][1]
            was_cached = True
        else:
            target_vec = model.encode(target_clean, convert_to_numpy=True, normalize_embeddings=True)
            self._EMBEDDING_CACHE[target_id] = (target_hash, target_vec)

        best_sim = -1.0
        best_cand = None

        texts_to_encode: List[str] = []
        cand_metas: List[Tuple[Dict[str, Any], str]] = []

        for cand in candidates:
            c_id = cand["project_id"]
            c_text = cand["clean_text"]
            c_hash = hashlib.md5(c_text.encode("utf-8")).hexdigest()

            if c_id in self._EMBEDDING_CACHE and self._EMBEDDING_CACHE[c_id][0] == c_hash:
                cand_vec = self._EMBEDDING_CACHE[c_id][1]
                sim = float(np.dot(target_vec, cand_vec))
                if sim > best_sim:
                    best_sim = sim
                    best_cand = cand
            else:
                texts_to_encode.append(c_text)
                cand_metas.append((cand, c_hash))

        # Batch encode any un-cached candidates
        if texts_to_encode:
            encoded_vecs = model.encode(texts_to_encode, convert_to_numpy=True, normalize_embeddings=True)
            for (cand, c_hash), c_vec in zip(cand_metas, encoded_vecs):
                c_id = cand["project_id"]
                self._EMBEDDING_CACHE[c_id] = (c_hash, c_vec)
                sim = float(np.dot(target_vec, c_vec))
                if sim > best_sim:
                    best_sim = sim
                    best_cand = cand

        sim_clamped = max(0.0, min(1.0, float(best_sim))) if best_cand else 0.0
        method = f"sentence-transformers/{self.model_name}"
        return sim_clamped, best_cand, method, was_cached

    def _compute_tfidf_similarities(
        self,
        target_clean: str,
        candidates: List[Dict[str, Any]]
    ) -> Tuple[float, Optional[Dict[str, Any]], str, bool]:
        """
        Computes cosine similarity using word & character n-gram TF-IDF vectorizer.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        all_texts = [target_clean] + [c["clean_text"] for c in candidates]
        vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            sublinear_tf=True
        )
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        target_vec = tfidf_matrix[0:1]
        cand_vecs = tfidf_matrix[1:]

        sims = cosine_similarity(target_vec, cand_vecs)[0]
        max_idx = int(np.argmax(sims))
        best_sim = float(sims[max_idx])
        best_cand = candidates[max_idx]

        sim_clamped = max(0.0, min(1.0, best_sim))
        return sim_clamped, best_cand, "tfidf_ngram_fallback", False

    # -------------------------------------------------------------------------
    # Helper: Scoring & False-Positive Reduction Logic
    # -------------------------------------------------------------------------

    def _compute_score_and_reason(
        self,
        target_project: Project,
        matched_candidate: Optional[Dict[str, Any]],
        raw_similarity: float,
    ) -> Tuple[float, str, str, Dict[str, Any]]:
        """
        Determines the normalized risk score (0-100) using semantic similarity
        augmented by structured location and category context to eliminate false positives.
        """
        if not matched_candidate:
            return 0.0, "NONE", "No candidate projects available for duplicate comparison.", {}

        matched_id = matched_candidate["project_id"]
        matched_title = matched_candidate["project_title"] or matched_id

        # 1. Location Matching Evaluation
        target_state = target_project.state_id
        cand_state = matched_candidate["state_id"]
        target_district = (target_project.district_name or "").strip().lower()
        cand_district = (matched_candidate["district_name"] or "").strip().lower()
        target_block = (target_project.block_name or "").strip().lower()
        cand_block = (matched_candidate["block_name"] or "").strip().lower()

        is_same_state = (target_state is not None and cand_state is not None and target_state == cand_state)
        is_same_district = (is_same_state and target_district and cand_district and target_district == cand_district)
        is_same_block = (is_same_district and target_block and cand_block and target_block == cand_block)

        if is_same_block:
            location_match = "same_block_and_district"
            location_factor = 1.25  # Substantial escalation: identical work in same block
        elif is_same_district:
            location_match = "same_district"
            location_factor = 1.15  # Notable escalation: same district
        elif is_same_state:
            location_match = "same_state"
            location_factor = 1.00  # Baseline regional comparison
        else:
            location_match = "different_state"
            location_factor = 0.60  # Strong dampener: standard wording across different states

        # 2. Category / Sector Matching Evaluation
        target_sector = (target_project.sector or "").strip().lower()
        cand_sector = (matched_candidate["sector"] or "").strip().lower()
        target_sub = (target_project.sub_sector or "").strip().lower()
        cand_sub = (matched_candidate["sub_sector"] or "").strip().lower()

        is_same_sector = bool(target_sector and cand_sector and target_sector == cand_sector)
        is_same_sub = bool(is_same_sector and target_sub and cand_sub and target_sub == cand_sub)

        if is_same_sub:
            sector_match = "same_sector_and_subsector"
            sector_factor = 1.10
        elif is_same_sector:
            sector_match = "same_sector"
            sector_factor = 1.00
        else:
            sector_match = "different_sector"
            sector_factor = 0.75  # Cross-sector terminology overlap

        # 3. Adjusted Similarity Calculation
        context_multiplier = location_factor * sector_factor
        adjusted_similarity = min(1.0, raw_similarity * (0.80 + 0.20 * context_multiplier))
        sim_pct = int(round(raw_similarity * 100))
        adj_pct = int(round(adjusted_similarity * 100))

        structured_info = {
            "location_match": location_match,
            "sector_match": sector_match,
            "location_factor": location_factor,
            "sector_factor": sector_factor,
            "adjusted_similarity": adjusted_similarity,
        }

        # Case 1: Normal (Similarity below possible threshold)
        if raw_similarity < self.threshold_possible:
            score = 0.0
            anomaly_type = "NONE"
            reason = (
                f"No duplicate or suspiciously similar project descriptions detected "
                f"(highest semantic match: {sim_pct}% with project '{matched_id}')."
            )
            return score, anomaly_type, reason, structured_info

        # Case 2: Cross-State Boilerplate Protection (False-Positive Reduction)
        # If projects are in completely different states and raw similarity < 0.95,
        # standard public-works phrasing across states is not a duplicate.
        if location_match == "different_state" and raw_similarity < 0.95:
            score = 15.0
            anomaly_type = "CROSS_STATE_TEMPLATE_PHRASING"
            reason = (
                f"Wording overlap ({sim_pct}%) with project '{matched_id}' reflects standard "
                f"sectoral phrasing across different states ({target_project.state_id} vs {cand_state}), "
                f"not a duplicate work."
            )
            return score, anomaly_type, reason, structured_info

        # Case 3: Possible Duplicate (Medium risk: score 30–59)
        if raw_similarity < self.threshold_strong:
            base_score = 30.0 + ((raw_similarity - self.threshold_possible) / (self.threshold_strong - self.threshold_possible)) * 25.0
            adjusted_score = base_score * context_multiplier

            # Clamp within MEDIUM tier (30-59) unless in same block
            final_score = max(30.0, min(59.0, adjusted_score))
            anomaly_type = "POSSIBLE_DUPLICATE"
            loc_desc = "same district" if is_same_district else ("same state" if is_same_state else "different state")
            reason = (
                f"Possible duplicate: Notable semantic similarity ({sim_pct}% match, adjusted: {adj_pct}%) "
                f"to project '{matched_id}' in {loc_desc}."
            )
            return final_score, anomaly_type, reason, structured_info

        # Case 4: Strong Duplicate (High / Critical risk: score 60–100)
        # S >= threshold_strong (>= 0.85)
        scale_range = max(0.01, 1.0 - self.threshold_strong)
        raw_score = 60.0 + ((raw_similarity - self.threshold_strong) / scale_range) * 35.0

        if is_same_block or (is_same_district and raw_similarity >= 0.92):
            # Critical escalation: near-identical proposal in same locality
            final_score = min(100.0, raw_score * 1.15 + 10.0)
            anomaly_type = "STRONG_DUPLICATE"
            reason = (
                f"High duplicate risk: Project description is highly similar ({sim_pct}% match) "
                f"to '{matched_id}' located in the same {target_project.district_name or 'district'}. "
                f"Potential redundant proposal or double-billing risk."
            )
        else:
            final_score = min(85.0, raw_score * context_multiplier)
            anomaly_type = "STRONG_DUPLICATE"
            loc_desc = f"district '{matched_candidate['district_name']}'" if cand_district else "another jurisdiction"
            reason = (
                f"Potential duplicate proposal: High semantic similarity ({sim_pct}% match) "
                f"with project '{matched_id}' in {loc_desc}."
            )

        return final_score, anomaly_type, reason, structured_info

    # -------------------------------------------------------------------------
    # Helper: Confidence Scoring
    # -------------------------------------------------------------------------

    def _compute_confidence(
        self,
        target_text_len: int,
        candidate_pool_size: int,
        method_used: str,
        target: Project,
    ) -> float:
        """
        Calculates diagnostic confidence based on text length, candidate corpus depth,
        vectorization method, and metadata completeness.
        """
        conf = 0.50

        # Description length signal
        if target_text_len >= 120:
            conf += 0.20
        elif target_text_len >= 60:
            conf += 0.15
        elif target_text_len >= 30:
            conf += 0.05

        # Candidate corpus depth
        if candidate_pool_size >= 20:
            conf += 0.15
        elif candidate_pool_size >= 10:
            conf += 0.10
        elif candidate_pool_size >= 3:
            conf += 0.05

        # Neural vs fallback fidelity
        if "sentence-transformers" in method_used:
            conf += 0.10
        else:
            conf += 0.05

        # Metadata completeness
        if target.district_name and target.state_id and target.sector:
            conf += 0.05

        return round(max(0.20, min(1.0, conf)), 3)

    # -------------------------------------------------------------------------
    # Cache Management Utilities
    # -------------------------------------------------------------------------

    @classmethod
    def clear_cache(cls) -> None:
        """Clears the class-level embedding cache."""
        cls._EMBEDDING_CACHE.clear()

    @classmethod
    def cache_size(cls) -> int:
        """Returns the number of cached project embeddings."""
        return len(cls._EMBEDDING_CACHE)
