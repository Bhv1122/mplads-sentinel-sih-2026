"""
backend/tests/test_analytics_visualizations.py
=============================================================================
Comprehensive unit and integration tests for Phase 10 Analytics Visualizations.
Tests endpoints:
- GET /analytics/overview
- GET /analytics/risk-distribution
- GET /analytics/states
- GET /analytics/districts
- GET /analytics/delays
- GET /analytics/cost-anomalies
- GET /analytics/trends
- GET /analytics/map
=============================================================================
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_analytics_overview():
    """Verify overview KPIs return correct types and positive values from real data."""
    response = client.get("/analytics/overview")
    assert response.status_code == 200
    data = response.json()

    assert "total_projects" in data
    assert data["total_projects"] > 0
    assert "high_risk_projects" in data
    assert "critical_risk_projects" in data
    assert "average_risk_score" in data
    assert 0 <= data["average_risk_score"] <= 100
    assert "flagged_percentage" in data
    assert "total_sanctioned_amount" in data
    assert "total_expenditure_amount" in data
    assert "overall_utilization_pct" in data
    assert "delayed_projects_count" in data
    assert "average_delay_days" in data


def test_analytics_overview_with_filters():
    """Verify overview responds cleanly with state and risk filters."""
    # Test with state filter
    response = client.get("/analytics/overview?state=Karnataka")
    assert response.status_code == 200
    data = response.json()
    assert data["total_projects"] >= 0

    # Test with risk level filter
    response_risk = client.get("/analytics/overview?risk_level=high")
    assert response_risk.status_code == 200
    data_risk = response_risk.json()
    assert data_risk["total_projects"] >= 0


def test_risk_distribution():
    """Verify risk distribution categories, percentages, and engine averages."""
    response = client.get("/analytics/risk-distribution")
    assert response.status_code == 200
    data = response.json()

    assert data["total_projects"] > 0
    dist = data["distribution"]
    assert "LOW" in dist
    assert "MEDIUM" in dist
    assert "HIGH" in dist
    assert "CRITICAL" in dist
    assert sum(dist.values()) == data["total_projects"]

    assert "percentages" in data
    assert "average_overall_score" in data
    assert "engine_averages" in data
    assert isinstance(data["engine_averages"], dict)


def test_states_analytics():
    """Verify state analytics sorting and comparative metrics."""
    response = client.get("/analytics/states?metric=risk_score&limit=10")
    assert response.status_code == 200
    data = response.json()

    assert data["total_states"] > 0
    assert len(data["states"]) > 0

    first = data["states"][0]
    assert "state_id" in first
    assert "state_name" in first
    assert "total_projects" in first
    assert "high_risk_projects" in first
    assert "critical_risk_projects" in first
    assert "average_risk_score" in first
    assert "average_delay_days" in first
    assert "cost_anomaly_count" in first
    assert "total_sanctioned" in first
    assert "total_expenditure" in first


def test_districts_analytics():
    """Verify district ranking and top-N limits."""
    response = client.get("/analytics/districts?limit=5")
    assert response.status_code == 200
    data = response.json()

    assert data["total_districts"] > 0
    assert len(data["districts"]) <= 5

    item = data["districts"][0]
    assert "district_name" in item
    assert "state_name" in item
    assert "total_projects" in item
    assert "average_risk_score" in item
    assert "average_delay_days" in item
    assert "total_sanctioned" in item


def test_delays_analytics():
    """Verify delay histogram buckets and top overdue works."""
    response = client.get("/analytics/delays")
    assert response.status_code == 200
    data = response.json()

    assert "total_projects_assessed" in data
    assert "on_time_count" in data
    assert "delayed_count" in data
    assert "severely_delayed_count" in data
    assert "average_delay_days" in data
    assert "max_delay_days" in data
    assert "delay_buckets" in data

    # Verify standard delay buckets exist in Dict
    buckets = data["delay_buckets"]
    assert "0 days" in buckets
    assert "1-30 days" in buckets
    assert "31-90 days" in buckets
    assert "91-180 days" in buckets
    assert "181-365 days" in buckets
    assert "365+ days" in buckets

    assert "top_delayed_projects" in data
    if len(data["top_delayed_projects"]) > 0:
        overdue = data["top_delayed_projects"][0]
        assert "project_id" in overdue
        assert "days_delayed" in overdue


def test_cost_anomalies_analytics():
    """Verify cost anomaly counts, rate, deviation buckets, and top deviations with peer context."""
    response = client.get("/analytics/cost-anomalies")
    assert response.status_code == 200
    data = response.json()

    assert "total_projects_assessed" in data
    assert "normal_cost_count" in data
    assert "cost_anomalous_count" in data
    assert "cost_anomaly_rate_pct" in data
    assert "deviation_distribution" in data
    assert "largest_deviations" in data

    if len(data["largest_deviations"]) > 0:
        top_dev = data["largest_deviations"][0]
        assert "project_id" in top_dev
        assert "evaluated_cost" in top_dev
        assert "peer_median" in top_dev
        assert "deviation_percentage" in top_dev
        assert "anomaly_type" in top_dev


def test_temporal_trends():
    """Verify longitudinal time-series trends."""
    response = client.get("/analytics/trends")
    assert response.status_code == 200
    data = response.json()

    assert data["granularity"] == "month"
    assert "trend_points" in data
    assert len(data["trend_points"]) > 0

    pt = data["trend_points"][0]
    assert "period" in pt
    assert "project_count" in pt
    assert "high_risk_count" in pt
    assert "average_risk_score" in pt
    assert "delayed_count" in pt
    assert "cost_anomalies_count" in pt
    assert "sanctioned_amount_cr" in pt
    assert "expenditure_amount_cr" in pt


def test_map_analytics():
    """Verify state choropleth geographic data with density scores."""
    response = client.get("/analytics/map?metric=projects")
    assert response.status_code == 200
    data = response.json()

    assert "states" in data
    assert len(data["states"]) > 0
    assert "active_metric" in data
    assert "max_value" in data

    st = data["states"][0]
    assert "state_code" in st
    assert "state_name" in st
    assert "total_projects" in st
    assert "high_risk_projects" in st
    assert "critical_risk_projects" in st
    assert "average_risk_score" in st
    assert "average_delay_days" in st
    assert 0.0 <= st["density_score"] <= 100.0


def test_map_analytics_with_state_filter():
    """Verify state filter on map endpoint."""
    response = client.get("/analytics/map?state=Bihar")
    assert response.status_code == 200
    data = response.json()
    assert "states" in data
    assert len(data["states"]) == 1
    assert data["states"][0]["state_name"] == "Bihar"


def test_states_sorting_metrics():
    """Verify sorting states by delays, cost_anomaly, and funds."""
    for m in ["delays", "cost_anomaly", "funds", "critical"]:
        res = client.get(f"/analytics/states?metric={m}&limit=5")
        assert res.status_code == 200
        assert len(res.json()["states"]) > 0


def test_districts_sorting():
    """Verify sorting districts by risk_score and delay."""
    for s in ["risk_score", "delay", "projects"]:
        res = client.get(f"/analytics/districts?sort_by={s}&limit=5")
        assert res.status_code == 200
        assert len(res.json()["districts"]) > 0
