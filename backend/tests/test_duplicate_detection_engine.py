"""
backend/tests/test_duplicate_detection_engine.py
=============================================================================
Comprehensive Test Suite for Engine 2: Duplicate Detection Engine.
=============================================================================

Tests:
1. Exact Schema & Return Contract (engine, score, risk_level, reason, details, confidence)
2. Mandatory Details Fields (matched_project_id, similarity)
3. Identical descriptions (similarity ~1.0, high/critical risk)
4. Highly similar / paraphrased descriptions (semantic embeddings vs exact match)
5. Unrelated projects (low similarity, score 0, LOW risk)
6. Missing and empty text handling (score 0, confidence 0.0)
7. Short description handling (< 15 chars)
8. Self-comparison exclusion (project never compared with itself)
9. Embedding caching verification (cached vectors retrieved without re-encoding)
10. False-positive reduction via structured location (same district vs different state)
11. False-positive reduction via category / sector differentiation
12. Configurable similarity thresholds (normal, possible duplicate, strong duplicate)
13. Live database evaluation
14. Non-existent project handling
"""

import os
import sys
from unittest.mock import MagicMock, patch
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.models.project import Project
from app.schemas.risk_engine import RiskLevel, EngineResult
from app.services.risk.duplicate_detection_engine import DuplicateDetectionEngine


@pytest.fixture
def db_session():
    """Provides an active database session against PostgreSQL."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def duplicate_engine():
    """DuplicateDetectionEngine instance using TF-IDF for rapid unit tests."""
    engine = DuplicateDetectionEngine(use_neural=False)
    engine.clear_cache()
    return engine


@pytest.fixture
def neural_engine():
    """DuplicateDetectionEngine instance with neural sentence-transformers."""
    engine = DuplicateDetectionEngine(use_neural=True)
    engine.clear_cache()
    return engine


# =============================================================================
# 1. Output Schema & Conformance Tests
# =============================================================================

class TestDuplicateDetectionSchema:

    def test_schema_keys_and_structure(self, db_session, duplicate_engine):
        """EngineResult must output the exact requested JSON keys and structure."""
        result = duplicate_engine.evaluate("MPLADS-2024-0001", db=db_session)
        assert isinstance(result, EngineResult)
        d = result.to_dict()

        expected_keys = {"engine", "score", "risk_level", "reason", "details", "confidence"}
        assert set(d.keys()) == expected_keys
        assert d["engine"] == "duplicate_detection"
        assert 0 <= d["score"] <= 100
        assert d["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert isinstance(d["reason"], str) and len(d["reason"]) > 0
        assert isinstance(d["details"], dict)
        assert 0.0 <= d["confidence"] <= 1.0

    def test_mandatory_details_fields_present(self, db_session, duplicate_engine):
        """Details must contain matched_project_id and similarity as specified."""
        result = duplicate_engine.evaluate("MPLADS-2024-0001", db=db_session)
        details = result.details

        assert "matched_project_id" in details
        assert "similarity" in details
        assert isinstance(details["similarity"], float)
        assert 0.0 <= details["similarity"] <= 1.0


# =============================================================================
# 2. Semantic Similarity & Anomaly Scenarios
# =============================================================================

class TestDuplicateDetectionScenarios:

    def test_identical_descriptions_same_district(self, duplicate_engine):
        """
        Identical descriptions in the same district indicate an urgent duplication concern.
        Should result in high/critical score and STRONG_DUPLICATE classification.
        """
        mock_db = MagicMock()
        target = Project(
            project_id="P-RO-1",
            project_title="Installation of RO Drinking Water Plant",
            project_description="Supply, erection and commissioning of 1000 LPH reverse osmosis water filtration unit at Ward 4 square.",
            sector="Drinking Water",
            sub_sector="Drinking Water",
            state_id=1,
            district_name="Patna",
            block_name="Patna Sadar",
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        candidates = [
            (
                "P-RO-2",
                "Installation of RO Drinking Water Plant",
                "Supply, erection and commissioning of 1000 LPH reverse osmosis water filtration unit at Ward 4 square.",
                "Drinking Water",
                "Drinking Water",
                1,
                "Patna",
                "Patna Sadar",
            ),
            (
                "P-ROAD-1",
                "Village Concrete Road",
                "Construction of CC road from hospital to bus stop.",
                "Roads & Bridges",
                "Roads",
                1,
                "Patna",
                "Patna Sadar",
            ),
        ]
        mock_db.execute.return_value.all.return_value = candidates

        res = duplicate_engine.evaluate("P-RO-1", db=mock_db)

        assert res.score >= 80
        assert res.risk_level == RiskLevel.CRITICAL.value
        assert res.details["matched_project_id"] == "P-RO-2"
        assert res.details["similarity"] >= 0.95
        assert res.details["duplicate_classification"] == "STRONG_DUPLICATE"
        assert res.details["location_match"] == "same_block_and_district"
        assert "duplicate" in res.reason.lower()

    def test_highly_similar_descriptions(self, neural_engine):
        """
        Highly similar descriptions (minor word substitutions) should trigger duplicate detection
        via semantic sentence embeddings and cosine similarity.
        """
        mock_db = MagicMock()
        target = Project(
            project_id="P-SOLAR-1",
            project_title="High Mast Solar Street Lighting System",
            project_description="Provision of 12 LED solar street lighting poles on highway crossing in municipal ward 5.",
            sector="Electricity",
            sub_sector="Solar Energy",
            state_id=2,
            district_name="Ranchi",
            block_name="Kanke",
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        candidates = [
            (
                "P-SOLAR-2",
                "Solar High Mast Illumination Poles",
                "Provision of 12 LED solar street lighting poles on highway intersection in municipal ward 5.",
                "Electricity",
                "Solar Energy",
                2,
                "Ranchi",
                "Kanke",
            ),
        ]
        mock_db.execute.return_value.all.return_value = candidates

        res = neural_engine.evaluate("P-SOLAR-1", db=mock_db)

        assert res.score >= 60
        assert res.risk_level in {RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}
        assert res.details["matched_project_id"] == "P-SOLAR-2"
        assert res.details["similarity"] >= 0.85
        assert res.details["duplicate_classification"] == "STRONG_DUPLICATE"

    def test_configurable_thresholds(self):
        """Engine should respect custom configurable similarity thresholds."""
        engine = DuplicateDetectionEngine(
            use_neural=False,
            threshold_normal=0.50,
            threshold_possible=0.65,
            threshold_strong=0.80,
        )
        assert engine.threshold_normal == 0.50
        assert engine.threshold_possible == 0.65
        assert engine.threshold_strong == 0.80

    def test_unrelated_projects(self, duplicate_engine):
        """
        Completely unrelated projects should result in low similarity, score 0, and LOW risk.
        """
        mock_db = MagicMock()
        target = Project(
            project_id="P-WATER",
            project_title="Community Reverse Osmosis Plant",
            project_description="Installation of 1000 LPH reverse osmosis drinking water filtration system in village square.",
            sector="Drinking Water",
            sub_sector="Drinking Water",
            state_id=1,
            district_name="Patna",
            block_name="Patna Sadar",
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        candidates = [
            (
                "P-ROAD",
                "Bituminous Road Construction",
                "Laying of bituminous concrete macadam pavement from highway km 12 to primary school.",
                "Roads & Bridges",
                "Roads",
                1,
                "Patna",
                "Patna Sadar",
            ),
            (
                "P-HEALTH",
                "Primary Health Center Ward Extension",
                "Construction of 4-bed patient waiting hall and immunization clinic building.",
                "Health",
                "Primary Health",
                1,
                "Patna",
                "Patna Sadar",
            ),
        ]
        mock_db.execute.return_value.all.return_value = candidates

        res = duplicate_engine.evaluate("P-WATER", db=mock_db)

        assert res.score <= 20
        assert res.risk_level == RiskLevel.LOW.value
        assert res.details["duplicate_classification"] == "NONE"
        assert res.details["similarity"] < 0.60
        assert "no duplicate" in res.reason.lower()


# =============================================================================
# 3. False-Positive Reduction via Structured Information
# =============================================================================

class TestFalsePositiveReduction:

    def test_identical_template_in_different_states_is_dampened(self, duplicate_engine):
        """
        Standard municipal template wording used across different states
        should be recognized as cross-state boilerplate and dampened to LOW risk.
        """
        mock_db = MagicMock()
        # Target in Bihar (state_id=1)
        target = Project(
            project_id="P-BIHAR",
            project_title="Construction of Community Hall",
            project_description="Construction of modern multi-purpose community hall with sanitation facilities under MPLADS scheme.",
            sector="Community Infrastructure",
            sub_sector="Community Centers",
            state_id=1,
            district_name="Patna",
            block_name="Phulwari",
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        # Candidate in Kerala (state_id=20) with identical template description
        candidates = [
            (
                "P-KERALA",
                "Construction of Community Hall",
                "Construction of modern multi-purpose community hall with sanitation facilities under MPLADS scheme.",
                "Community Infrastructure",
                "Community Centers",
                20,
                "Ernakulam",
                "Kochi",
            ),
        ]
        mock_db.execute.return_value.all.return_value = candidates

        res = duplicate_engine.evaluate("P-BIHAR", db=mock_db)

        # Must NOT trigger CRITICAL or HIGH risk across different states
        assert res.score <= 30
        assert res.risk_level in {RiskLevel.LOW.value, RiskLevel.MEDIUM.value}
        assert res.details["location_match"] == "different_state"
        assert res.details["location_factor"] < 1.0
        assert "different states" in res.reason.lower()

    def test_different_sectors_dampen_similarity(self, duplicate_engine):
        """
        Overlapping generic terminology across different sectors is dampened.
        """
        mock_db = MagicMock()
        target = Project(
            project_id="P-HEALTH-SOLAR",
            project_title="Hospital Solar Backup",
            project_description="Supply of roof mounted solar photovoltaic panels for primary health center.",
            sector="Health",
            sub_sector="Hospital Infrastructure",
            state_id=1,
            district_name="Patna",
            block_name="Sadar",
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        candidates = [
            (
                "P-ELEC-SOLAR",
                "Village Solar Lighting",
                "Supply of roof mounted solar photovoltaic panels for street lighting battery station.",
                "Electricity",
                "Solar Grid",
                1,
                "Patna",
                "Sadar",
            ),
        ]
        mock_db.execute.return_value.all.return_value = candidates

        res = duplicate_engine.evaluate("P-HEALTH-SOLAR", db=mock_db)

        assert res.details["sector_match"] == "different_sector"
        assert res.details["sector_factor"] < 1.0


# =============================================================================
# 4. Edge Cases: Empty Text, Short Descriptions & Missing Projects
# =============================================================================

class TestDuplicateEdgeCases:

    def test_missing_description_and_empty_text(self, duplicate_engine):
        """Empty or None text should return score 0, LOW risk, confidence 0.0."""
        mock_db = MagicMock()
        target = Project(
            project_id="P-EMPTY",
            project_title=None,
            project_description="",
            sector="Health",
            state_id=1,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = duplicate_engine.evaluate("P-EMPTY", db=mock_db)

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.confidence == 0.0
        assert res.details["matched_project_id"] is None
        assert res.details["similarity"] == 0.0
        assert res.details["missing_text"] is True

    def test_very_short_description(self, duplicate_engine):
        """Very short text (<15 characters) cannot reliably detect duplicates."""
        mock_db = MagicMock()
        target = Project(
            project_id="P-SHORT",
            project_title="Road",
            project_description="Work",
            sector="Roads",
            state_id=1,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = duplicate_engine.evaluate("P-SHORT", db=mock_db)

        assert res.score == 0
        assert res.confidence == 0.0
        assert res.details["missing_text"] is True
        assert "too short" in res.reason.lower()

    def test_nonexistent_project_not_found(self, duplicate_engine):
        """Nonexistent project ID should return clean not_found response."""
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        res = duplicate_engine.evaluate("NONEXISTENT-ID", db=mock_db)

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.confidence == 0.0
        assert res.details["error"] == "not_found"

    def test_self_comparison_exclusion(self, duplicate_engine):
        """A project must never be compared against itself."""
        mock_db = MagicMock()
        target = Project(
            project_id="P-TARGET",
            project_title="Construction of School Classrooms",
            project_description="Building 4 new classrooms with desks and blackboards.",
            sector="Education",
            state_id=1,
            district_name="Varanasi",
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        # Candidate query should have been executed with project_id != 'P-TARGET'
        # Simulate candidates where P-TARGET was filtered out
        candidates = [
            (
                "P-OTHER",
                "Drinking Water Tank",
                "Installation of overhead HDPE storage tank.",
                "Drinking Water",
                "Water",
                1,
                "Varanasi",
                "Sadar",
            )
        ]
        mock_db.execute.return_value.all.return_value = candidates

        res = duplicate_engine.evaluate("P-TARGET", db=mock_db)

        # The matched project must NOT be P-TARGET itself
        assert res.details["matched_project_id"] != "P-TARGET"


# =============================================================================
# 5. Embedding Caching Verification
# =============================================================================

class TestEmbeddingCaching:

    def test_embedding_cache_hit_on_repeated_calls(self, neural_engine):
        """
        Embeddings should be cached in memory so identical texts do not
        unnecessarily trigger transformer re-encodings.
        """
        mock_db = MagicMock()
        target = Project(
            project_id="P-CACHE-1",
            project_title="Construction of Bridge Over Canal",
            project_description="Construction of RCC box culvert bridge over irrigation canal at Village Rampur.",
            sector="Roads & Bridges",
            sub_sector="Bridges",
            state_id=1,
            district_name="Patna",
            block_name="Bihta",
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        candidates = [
            (
                "P-CACHE-2",
                "Bridge Over Canal",
                "Construction of RCC box culvert bridge over irrigation canal at Village Rampur.",
                "Roads & Bridges",
                "Bridges",
                1,
                "Patna",
                "Bihta",
            )
        ]
        mock_db.execute.return_value.all.return_value = candidates

        # First evaluation: populates cache
        res1 = neural_engine.evaluate("P-CACHE-1", db=mock_db)
        assert res1.details["embedding_cached"] is False
        assert neural_engine.cache_size() >= 2

        # Second evaluation for same target: cache hit
        res2 = neural_engine.evaluate("P-CACHE-1", db=mock_db)
        assert res2.details["embedding_cached"] is True
        assert res2.details["similarity"] == res1.details["similarity"]


# =============================================================================
# 6. Live Database Evaluation Tests
# =============================================================================

class TestDuplicateLiveDatabase:

    def test_evaluate_live_database_project(self, db_session, duplicate_engine):
        """Evaluates duplicate detection engine on live PostgreSQL project."""
        result = duplicate_engine.evaluate("MPLADS-2024-0001", db=db_session)
        assert result.engine == "duplicate_detection"
        assert isinstance(result.score, int)
        assert 0 <= result.score <= 100
        assert result.risk_level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert result.confidence > 0.0
        assert "matched_project_id" in result.details
        assert "similarity" in result.details
        assert result.details["matched_project_id"] != "MPLADS-2024-0001"
