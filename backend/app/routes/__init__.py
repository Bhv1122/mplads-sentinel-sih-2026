"""
backend/app/routes package
"""

from app.routes.projects import router as projects_router
from app.routes.analytics import router as analytics_router, high_risk_router
from app.routes.agencies import router as agencies_router
from app.routes.roles import router as roles_router

__all__ = [
    "projects_router",
    "analytics_router",
    "high_risk_router",
    "agencies_router",
    "roles_router",
]
