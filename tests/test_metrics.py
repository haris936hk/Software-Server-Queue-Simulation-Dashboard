import pandas as pd
import pytest

import app


def test_time_weighted_average_queue_length_manual_example():
    queue_df = pd.DataFrame(
        {
            "time_minutes": [0, 2, 5, 10],
            "queue_length": [0, 3, 1, 0],
        }
    )

    result = app.calculate_time_weighted_average_queue_length(queue_df, 10)

    assert result == pytest.approx(1.4)


def test_time_weighted_average_includes_final_interval():
    queue_df = pd.DataFrame(
        {
            "time_minutes": [0, 2],
            "queue_length": [0, 4],
        }
    )

    result = app.calculate_time_weighted_average_queue_length(queue_df, 6)

    assert result == pytest.approx(16 / 6)


def test_time_weighted_average_empty_queue_is_zero():
    queue_df = pd.DataFrame(columns=app.QUEUE_COLUMNS)

    assert app.calculate_time_weighted_average_queue_length(queue_df, 10) == 0


def test_calculate_metrics_normal_values():
    requests_df = pd.DataFrame(
        [
            {
                "request_id": 1,
                "arrival_time_minutes": 0,
                "service_start_time_minutes": 0,
                "completion_time_minutes": 5 / 60,
                "waiting_time_seconds": 1,
                "service_time_seconds": 4,
                "response_time_seconds": 5,
            },
            {
                "request_id": 2,
                "arrival_time_minutes": 1,
                "service_start_time_minutes": 1,
                "completion_time_minutes": 1 + 7 / 60,
                "waiting_time_seconds": 3,
                "service_time_seconds": 4,
                "response_time_seconds": 7,
            },
        ],
        columns=app.REQUEST_COLUMNS,
    )
    queue_df = pd.DataFrame(
        {"time_minutes": [0, 10], "queue_length": [0, 0]},
        columns=app.QUEUE_COLUMNS,
    )

    metrics = app.calculate_metrics(
        requests_df,
        queue_df,
        observed_end_time_minutes=10,
        arrival_rate_per_minute=12,
        average_service_time_seconds=5,
        number_of_servers=2,
        simulation_duration_minutes=10,
        sla_threshold_seconds=5,
    )

    assert metrics["completed_requests"] == 2
    assert metrics["average_waiting_time_seconds"] == pytest.approx(2)
    assert metrics["average_response_time_seconds"] == pytest.approx(6)
    assert metrics["sla_breach_rate"] == pytest.approx(0.5)
    assert metrics["throughput"] == pytest.approx(0.2)
    assert metrics["average_queue_length"] == pytest.approx(0)


def test_calculate_metrics_empty_requests_is_safe():
    queue_df = pd.DataFrame(
        {"time_minutes": [0, 10], "queue_length": [0, 0]},
        columns=app.QUEUE_COLUMNS,
    )

    metrics = app.calculate_metrics(
        app.empty_requests_df(),
        queue_df,
        observed_end_time_minutes=10,
        arrival_rate_per_minute=1,
        average_service_time_seconds=1,
        number_of_servers=1,
        simulation_duration_minutes=10,
        sla_threshold_seconds=1,
    )

    assert metrics["completed_requests"] == 0
    assert metrics["average_waiting_time_seconds"] is None
    assert metrics["average_response_time_seconds"] is None
    assert metrics["sla_breach_rate"] == 0
    assert metrics["throughput"] == 0


def test_calculate_utilization_normal_case():
    assert app.calculate_utilization(20, 5, 3) == pytest.approx(20 / 36)


def test_calculate_utilization_high_case():
    assert app.calculate_utilization(35, 5, 2) == pytest.approx(35 / 24)


def test_sla_breach_boundary_uses_strictly_greater_than_threshold():
    requests_df = pd.DataFrame(
        [
            {
                "request_id": 1,
                "arrival_time_minutes": 0,
                "service_start_time_minutes": 0,
                "completion_time_minutes": 5 / 60,
                "waiting_time_seconds": 0,
                "service_time_seconds": 5,
                "response_time_seconds": 5,
            },
            {
                "request_id": 2,
                "arrival_time_minutes": 0,
                "service_start_time_minutes": 0,
                "completion_time_minutes": 6 / 60,
                "waiting_time_seconds": 0,
                "service_time_seconds": 6,
                "response_time_seconds": 6,
            },
        ],
        columns=app.REQUEST_COLUMNS,
    )
    queue_df = pd.DataFrame(
        {"time_minutes": [0, 1], "queue_length": [0, 0]},
        columns=app.QUEUE_COLUMNS,
    )

    metrics = app.calculate_metrics(
        requests_df,
        queue_df,
        observed_end_time_minutes=1,
        arrival_rate_per_minute=1,
        average_service_time_seconds=5,
        number_of_servers=1,
        simulation_duration_minutes=1,
        sla_threshold_seconds=5,
    )

    assert metrics["sla_breach_rate"] == pytest.approx(0.5)


def test_display_format_helpers():
    assert app.format_seconds(None) == "N/A"
    assert app.format_seconds(1.234) == "1.23 sec"
    assert app.format_number(None) == "N/A"
    assert app.format_number(2.345) == "2.35"
    assert app.format_percent(0.1234) == "12.3%"
    assert app.format_percent(0.1234, decimals=2) == "12.34%"
