import numpy as np
import pandas as pd
import pytest

import app


def test_run_simulation_basic_return_types():
    workload_df = app.generate_workload(20, 5, 60, 42)
    requests_df, queue_df, observed_end = app.run_simulation(workload_df, 3, 60)

    assert isinstance(requests_df, pd.DataFrame)
    assert isinstance(queue_df, pd.DataFrame)
    assert observed_end >= 60


def test_run_simulation_request_event_columns():
    workload_df = app.generate_workload(20, 5, 60, 42)
    requests_df, _, _ = app.run_simulation(workload_df, 3, 60)

    assert list(requests_df.columns) == app.REQUEST_COLUMNS


def test_run_simulation_with_manual_deterministic_workload():
    workload_df = pd.DataFrame(
        [
            {
                "request_id": 1,
                "arrival_time_minutes": 0.0,
                "service_time_minutes": 2.0,
                "service_time_seconds": 120.0,
            },
            {
                "request_id": 2,
                "arrival_time_minutes": 1.0,
                "service_time_minutes": 1.0,
                "service_time_seconds": 60.0,
            },
            {
                "request_id": 3,
                "arrival_time_minutes": 1.5,
                "service_time_minutes": 0.5,
                "service_time_seconds": 30.0,
            },
        ],
        columns=app.WORKLOAD_COLUMNS,
    )

    requests_df, queue_df, observed_end = app.run_simulation(
        workload_df, number_of_servers=1, simulation_duration_minutes=2
    )
    requests_df = requests_df.sort_values("request_id").reset_index(drop=True)

    assert requests_df["request_id"].tolist() == [1, 2, 3]
    assert requests_df["service_start_time_minutes"].tolist() == pytest.approx(
        [0.0, 2.0, 3.0]
    )
    assert requests_df["completion_time_minutes"].tolist() == pytest.approx(
        [2.0, 3.0, 3.5]
    )
    assert requests_df["waiting_time_seconds"].tolist() == pytest.approx(
        [0.0, 60.0, 90.0]
    )
    assert requests_df["response_time_seconds"].tolist() == pytest.approx(
        [120.0, 120.0, 120.0]
    )
    assert observed_end == pytest.approx(3.5)
    assert queue_df.iloc[-1]["time_minutes"] == pytest.approx(observed_end)


def test_run_simulation_event_timing_correctness():
    workload_df = app.generate_workload(20, 5, 60, 42)
    requests_df, _, _ = app.run_simulation(workload_df, 3, 60)

    assert (requests_df["service_start_time_minutes"] >= requests_df["arrival_time_minutes"]).all()
    assert (
        requests_df["completion_time_minutes"]
        >= requests_df["service_start_time_minutes"]
    ).all()
    assert (requests_df["waiting_time_seconds"] >= 0).all()
    assert (requests_df["service_time_seconds"] > 0).all()
    assert (
        requests_df["response_time_seconds"] + 1e-9
        >= requests_df["service_time_seconds"]
    ).all()
    assert np.allclose(
        requests_df["response_time_seconds"],
        requests_df["waiting_time_seconds"] + requests_df["service_time_seconds"],
    )


def test_run_simulation_all_arrived_requests_complete_and_observed_end_matches():
    workload_df = app.generate_workload(35, 5, 60, 42)
    requests_df, _, observed_end = app.run_simulation(workload_df, 2, 60)

    assert len(requests_df) == len(workload_df)
    assert observed_end == pytest.approx(
        max(60, requests_df["completion_time_minutes"].max())
    )


def test_run_simulation_empty_workload_is_safe():
    workload_df = pd.DataFrame(columns=app.WORKLOAD_COLUMNS)
    requests_df, queue_df, observed_end = app.run_simulation(workload_df, 1, 10)

    assert requests_df.empty
    assert list(requests_df.columns) == app.REQUEST_COLUMNS
    assert list(queue_df.columns) == app.QUEUE_COLUMNS
    assert queue_df.iloc[0]["time_minutes"] == 0
    assert queue_df.iloc[0]["queue_length"] == 0
    assert observed_end == 10


def test_single_server_congested_workload_has_waiting_or_queueing():
    workload_df = app.generate_workload(35, 20, 60, 42)
    requests_df, queue_df, observed_end = app.run_simulation(workload_df, 1, 60)
    metrics = app.calculate_metrics(
        requests_df,
        queue_df,
        observed_end,
        arrival_rate_per_minute=35,
        average_service_time_seconds=20,
        number_of_servers=1,
        simulation_duration_minutes=60,
        sla_threshold_seconds=60,
    )

    assert metrics["average_waiting_time_seconds"] > 0
    assert metrics["average_queue_length"] > 0


def test_more_servers_do_not_worsen_same_workload_performance():
    workload_df = app.generate_workload(35, 5, 60, 42)
    baseline_requests, _, _ = app.run_simulation(workload_df, 2, 60)
    optimized_requests, _, _ = app.run_simulation(workload_df, 4, 60)

    assert set(baseline_requests["request_id"]) == set(optimized_requests["request_id"])
    assert len(baseline_requests) == len(optimized_requests) == len(workload_df)
    assert (
        optimized_requests["waiting_time_seconds"].mean()
        <= baseline_requests["waiting_time_seconds"].mean()
    )
    assert (
        optimized_requests["response_time_seconds"].mean()
        <= baseline_requests["response_time_seconds"].mean()
    )


def test_queue_event_tracking_schema_and_final_interval():
    workload_df = app.generate_workload(20, 5, 60, 42)
    _, queue_df, observed_end = app.run_simulation(workload_df, 3, 60)

    assert list(queue_df.columns) == app.QUEUE_COLUMNS
    assert queue_df.iloc[0]["time_minutes"] == 0
    assert queue_df.iloc[0]["queue_length"] == 0
    assert (queue_df["queue_length"] >= 0).all()
    assert queue_df["time_minutes"].is_monotonic_increasing
    assert queue_df.iloc[-1]["time_minutes"] == pytest.approx(observed_end)


@pytest.mark.parametrize(
    "arrival_rate,service_time,servers,duration,sla,seed",
    [
        (1, 1, 1, 10, 1, 1),
        (100, 30, 1, 240, 60, 42),
    ],
)
def test_edge_case_valid_inputs_do_not_crash(
    arrival_rate, service_time, servers, duration, sla, seed
):
    workload_df = app.generate_workload(arrival_rate, service_time, duration, seed)
    requests_df, queue_df, observed_end = app.run_simulation(
        workload_df, servers, duration
    )
    metrics = app.calculate_metrics(
        requests_df,
        queue_df,
        observed_end,
        arrival_rate,
        service_time,
        servers,
        duration,
        sla,
    )

    assert list(workload_df.columns) == app.WORKLOAD_COLUMNS
    assert list(requests_df.columns) == app.REQUEST_COLUMNS
    assert list(queue_df.columns) == app.QUEUE_COLUMNS
    assert metrics["completed_requests"] == len(requests_df)


def test_same_workload_comparison_preserves_request_ids_and_service_times():
    workload_df = app.generate_workload(35, 5, 60, 42)
    baseline_requests, _, _ = app.run_simulation(workload_df, 2, 60)
    optimized_requests, _, _ = app.run_simulation(workload_df, 4, 60)

    baseline = baseline_requests.sort_values("request_id").reset_index(drop=True)
    optimized = optimized_requests.sort_values("request_id").reset_index(drop=True)
    workload = workload_df.sort_values("request_id").reset_index(drop=True)

    assert baseline["request_id"].tolist() == optimized["request_id"].tolist()
    assert baseline["request_id"].tolist() == workload["request_id"].tolist()
    assert np.allclose(
        baseline["service_time_seconds"],
        optimized["service_time_seconds"],
    )
    assert np.allclose(
        baseline["service_time_seconds"],
        workload["service_time_seconds"],
    )
