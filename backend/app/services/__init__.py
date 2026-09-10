"""
backend/app/services package
"""

try:
    from app.services.project_service import ProjectService
    from app.services.analytics_service import AnalyticsService
    from app.services.historical_comparison_service import HistoricalComparisonService
    from app.services.historical_risk_integration_service import (
        HistoricalRiskIntegrationService,
        historical_risk_integration_service,
    )
except ImportError:
    from backend.app.services.project_service import ProjectService
    from backend.app.services.analytics_service import AnalyticsService
    from backend.app.services.historical_comparison_service import HistoricalComparisonService
    from backend.app.services.historical_risk_integration_service import (
        HistoricalRiskIntegrationService,
        historical_risk_integration_service,
    )



def __getattr__(name: str):
    if name == "RiskEngine":
        try:
            from app.services.risk_engine import RiskEngine
        except ImportError:
            from backend.app.services.risk_engine import RiskEngine
        return RiskEngine
    if name in ("BatchRiskService", "BatchRiskSummary", "batch_risk_service"):
        try:
            from app.services.risk.batch_risk_service import (
                BatchRiskService,
                BatchRiskSummary,
                batch_risk_service,
            )
        except ImportError:
            from backend.app.services.risk.batch_risk_service import (
                BatchRiskService,
                BatchRiskSummary,
                batch_risk_service,
            )
    if name in ("ExplainabilityService", "explainability_service"):
        try:
            from app.services.explainability_service import (
                ExplainabilityService,
                explainability_service,
            )
        except ImportError:
            from backend.app.services.explainability_service import (
                ExplainabilityService,
                explainability_service,
            )
        return locals()[name]
    if name in (
        "EvidenceGenerator",
        "evidence_generator",
        "format_currency",
        "format_percentage",
        "format_percentage_points",
        "format_ratio",
        "format_multiplier",
        "format_duration",
        "format_score",
        "format_date",
        "parse_numerical_value",
    ):
        try:
            from app.services.evidence_generator import (
                EvidenceGenerator,
                evidence_generator,
                format_currency,
                format_percentage,
                format_percentage_points,
                format_ratio,
                format_multiplier,
                format_duration,
                format_score,
                format_date,
                parse_numerical_value,
            )
        except ImportError:
            from backend.app.services.evidence_generator import (
                EvidenceGenerator,
                evidence_generator,
                format_currency,
                format_percentage,
                format_percentage_points,
                format_ratio,
                format_multiplier,
                format_duration,
                format_score,
                format_date,
                parse_numerical_value,
            )
        return locals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "ProjectService",
    "AnalyticsService",
    "RiskEngine",
    "BatchRiskService",
    "BatchRiskSummary",
    "batch_risk_service",
    "ExplainabilityService",
    "explainability_service",
    "EvidenceGenerator",
    "evidence_generator",
    "format_currency",
    "format_percentage",
    "format_percentage_points",
    "format_ratio",
    "format_multiplier",
    "format_duration",
    "format_score",
    "format_date",
    "parse_numerical_value",
    "HistoricalComparisonService",
    "HistoricalRiskIntegrationService",
    "historical_risk_integration_service",
]
