import pytest

import app


@pytest.mark.parametrize(
    "utilization,expected_status",
    [
        (0.50, "Healthy / Possibly Over-Provisioned"),
        (0.75, "Good Utilization"),
        (0.90, "High Risk"),
        (1.00, "Overloaded"),
        (1.50, "Overloaded"),
        (0.70, "Good Utilization"),
        (0.85, "High Risk"),
    ],
)
def test_bottleneck_status_classification(utilization, expected_status):
    status, explanation, level = app.get_bottleneck_status(utilization)

    assert status == expected_status
    assert explanation
    assert level in {"success", "info", "warning", "error"}


def test_recommend_server_count_healthy_scenario():
    recommendation = app.recommend_server_count(20, 5)

    assert recommendation["recommended_servers"] == 2
    assert recommendation["recommended_utilization"] == pytest.approx(20 / 24)
    assert recommendation["workload_may_still_be_too_high"] is False


def test_recommend_server_count_overloaded_scenario():
    recommendation = app.recommend_server_count(35, 5)

    assert recommendation["recommended_servers"] == 4
    assert recommendation["recommended_utilization"] == pytest.approx(35 / 48)
    assert recommendation["workload_may_still_be_too_high"] is False


def test_recommend_server_count_extreme_workload_warns_at_max_servers():
    recommendation = app.recommend_server_count(100, 30)

    assert recommendation["recommended_servers"] == 10
    assert recommendation["recommended_utilization"] == pytest.approx(5.0)
    assert recommendation["workload_may_still_be_too_high"] is True


def test_recommend_server_count_accepts_exact_target_boundary():
    recommendation = app.recommend_server_count(
        arrival_rate_per_minute=17,
        average_service_time_seconds=3,
        max_servers=10,
        target_utilization=0.85,
    )

    assert recommendation["recommended_servers"] == 1
    assert recommendation["recommended_utilization"] == pytest.approx(0.85)
    assert recommendation["workload_may_still_be_too_high"] is False
