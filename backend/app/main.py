"""
backend/app/main.py
=============================================================================
FastAPI Application Entry Point for MPLADS Governance & Project Analytics.
=============================================================================
"""

import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, Any

# Ensure backend directory is on sys.path so `app.*` imports work from both
# the backend directory (uvicorn app.main:app) and project root (uvicorn backend.app.main:app)
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, status, HTTPException, Request
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse, RedirectResponse

from app.database import check_db_connection, engine
from app.routes import projects_router, analytics_router, high_risk_router, agencies_router, roles_router
try:
    from app.config import settings
except ImportError:
    from backend.app.config import settings

logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown event handler.
    Verifies database connectivity on startup.
    """
    print("=" * 70)
    print("Starting MPLADS Governance & Analytics API Service...")
    is_connected = check_db_connection()
    if is_connected:
        print("  Database Connection: ONLINE (PostgreSQL 'mplads_db')")
    else:
        print("  WARNING: Database connection failed! Check .env credentials.")
    print("  Interactive OpenAPI Docs: http://localhost:8000/docs")
    print("  ReDoc Documentation:     http://localhost:8000/redoc")
    print("=" * 70)
    yield
    print("\nShutting down MPLADS API Service...")
    engine.dispose()


# App title and OpenAPI metadata
app = FastAPI(
    title="MPLADS Project Intelligence & Governance API",
    description="""
# Ministry of Statistics and Programme Implementation (MoSPI)
## Member of Parliament Local Area Development Scheme (MPLADS) Backend API

This production API delivers:
- **Project Microdata Lifecycle Management**: Track developmental works from MP recommendation to audit completion.
- **Full-Text & Fuzzy Search**: Sub-second queries powered by PostgreSQL `TSVECTOR` full-text search and `pg_trgm` fuzzy matching.
- **Predictive Risk Analytics**: Automated escalation of project delay, cost overrun, and non-completion likelihood.
- **Deterministic Explainability & Audit Evidence**: Structured 'Why Was This Flagged?' diagnostic breakdowns with empirical baselines and point-by-point risk contributions.
- **National & State Governance Dashboards**: Real-time surveillance of stalled works, SC/ST equity compliance, and 33-year Union Budget trends.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Configure Cross-Origin Resource Sharing (CORS) suitable for any frontend (React, Next.js, Vite, Vue)
origins = settings.cors_origin_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if "*" not in origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@app.get(
    "/",
    tags=["Health & Status"],
    summary="Root API Information / Sentinel Portal"
)
def root_info(request: Request) -> Any:
    """
    Returns API operational metadata or redirects browser clients to the Sentinel Dashboard.
    """
    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header:
        return RedirectResponse(url="/ui/")

    return {
        "status": "online",
        "service": "MPLADS Governance & Analytics API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
        "health_check": "/health",
        "endpoints": {
            "ui": "/ui/",
            "projects": "/projects",
            "project_detail": "/projects/{id}",
            "analytics": "/analytics",
            "high_risk": "/high-risk"
        }
    }


@app.get(
    "/health",
    tags=["Health & Status"],
    summary="System Health & Database Connectivity Check"
)
@app.get(
    "/api/health",
    tags=["Health & Status"],
    summary="System Health & Database Connectivity Check (API Alias)"
)
def health_check() -> Dict[str, Any]:
    """
    Verifies that the backend is running and actively checks PostgreSQL database connectivity.
    Returns HTTP 200 if connected, or HTTP 503 if database connection fails.
    """
    db_healthy = check_db_connection()
    if not db_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend is running, but PostgreSQL database connectivity failed."
        )

    return {
        "status": "healthy",
        "backend": "running",
        "database": "connected",
        "database_name": "mplads_db"
    }


# =============================================================================
# Mount Modular API Routers
# =============================================================================

app.include_router(projects_router)
app.include_router(projects_router, prefix="/api/v1")
app.include_router(analytics_router)
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(high_risk_router)
app.include_router(high_risk_router, prefix="/api/v1")
app.include_router(agencies_router)
app.include_router(agencies_router, prefix="/api/v1")
app.include_router(roles_router)
app.include_router(roles_router, prefix="/api/v1")


# =============================================================================
# Frontend UI Shortcuts and Routes
# =============================================================================

# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles

_frontend_dir = os.path.join(_backend_dir, "..", "frontend")
if not os.path.exists(_frontend_dir):
    os.makedirs(_frontend_dir, exist_ok=True)

@app.get("/ui/overview", include_in_schema=False)
def redirect_to_overview():
    return RedirectResponse(url="/ui/overview_dashboard_mplads_sentinel/")

@app.get("/ui/projects", include_in_schema=False)
def redirect_to_projects():
    return RedirectResponse(url="/ui/projects_explorer_mplads_sentinel/")

@app.get("/ui/project-detail", include_in_schema=False)
def redirect_to_project_detail(id: Optional[str] = None):
    url = "/ui/project_risk_profile_p_10291_multi_purpose_community_hall/"
    if id:
        url += f"?id={id}"
    return RedirectResponse(url=url)

@app.get("/ui/analytics", include_in_schema=False)
def redirect_to_analytics():
    return RedirectResponse(url="/ui/risk_analytics_portfolio_risk_telemetry_anomaly_intelligence/")

@app.get("/ui/spatial", include_in_schema=False)
def redirect_to_spatial():
    return RedirectResponse(url="/ui/geographic_analysis_spatial_risk_intelligence/")

@app.get("/ui/audits", include_in_schema=False)
@app.get("/ui/investigations", include_in_schema=False)
def redirect_to_investigations():
    return RedirectResponse(url="/ui/investigation_queue_case_management_review_triage/")

@app.get("/ui/assistant", include_in_schema=False)
def redirect_to_assistant():
    return RedirectResponse(url="/ui/ai_audit_assistant_mplads_sentinel/")

@app.get("/ui/system-status", include_in_schema=False)
def redirect_to_system_status():
    return RedirectResponse(url="/ui/data_system_status_mplads_sentinel/")

@app.get("/ui/consumer", include_in_schema=False)
@app.get("/ui/consumer/", include_in_schema=False)
def redirect_to_consumer():
    return RedirectResponse(url="/ui/consumer_portal/")

@app.get("/ui/nodal-head", include_in_schema=False)
@app.get("/ui/nodal-head/", include_in_schema=False)
def redirect_to_nodal_head():
    return RedirectResponse(url="/ui/nodal_head_portal/")

@app.get("/ui/site-executer", include_in_schema=False)
@app.get("/ui/site-executer/", include_in_schema=False)
def redirect_to_site_executer():
    return RedirectResponse(url="/ui/site_executer_portal/")

@app.get("/ui/overview", include_in_schema=False)
@app.get("/ui/overview/", include_in_schema=False)
def redirect_to_overview():
    return RedirectResponse(url="/ui/overview_dashboard_mplads_sentinel/")

@app.get("/ui/projects", include_in_schema=False)
@app.get("/ui/projects/", include_in_schema=False)
def redirect_to_projects():
    return RedirectResponse(url="/ui/projects_explorer_mplads_sentinel/")

@app.get("/ui/login", include_in_schema=False)
def redirect_to_login():
    return RedirectResponse(url="/ui/authorized_officer_login_mplads_sentinel/")

@app.get("/brochure", include_in_schema=False)
@app.get("/ui/brochure", include_in_schema=False)
def redirect_to_brochure():
    return RedirectResponse(url="/ui/brochure/")

app.mount("/ui", StaticFiles(directory=_frontend_dir, html=True), name="ui")


# =============================================================================
# Exception Handlers (Prevent Stack Trace Leakage)
# =============================================================================

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Clean HTTP exception handler without exposing stack traces."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catches all unhandled exceptions, logs them securely, and returns a clean error response.
    Guarantees that internal Python stack traces, SQL syntax, or server details never leak to API clients.
    """
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred while processing the request.",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        }
    )


if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    import uvicorn
    host = settings.APP_HOST
    port = settings.APP_PORT
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
