import numpy as np
import pandas as pd

import app


def assert_workload_schema(workload_df: pd.DataFrame, duration_minutes: int) -> None:
    assert isinstance(workload_df, pd.DataFrame)
    assert list(workload_df.columns) == app.WORKLOAD_COLUMNS

    if workload_df.empty:
        return

    assert workload_df["request_id"].is_unique
    assert workload_df["arrival_time_minutes"].is_monotonic_increasing
    assert (workload_df["arrival_time_minutes"] >= 0).all()
    assert (workload_df["arrival_time_minutes"] <= duration_minutes).all()
    assert (workload_df["service_time_minutes"] > 0).all()
    assert (workload_df["service_time_seconds"] > 0).all()
    assert np.allclose(
        workload_df["service_time_seconds"],
        workload_df["service_time_minutes"] * 60,
    )


def test_generate_workload_basic_schema_and_values():
    workload_df = app.generate_workload(20, 5, 60, 42)

    assert_workload_schema(workload_df, duration_minutes=60)
    assert not workload_df.empty


def test_generate_workload_is_deterministic_for_same_seed():
    workload_a = app.generate_workload(20, 5, 60, 42)
    workload_b = app.generate_workload(20, 5, 60, 42)

    pd.testing.assert_frame_equal(workload_a, workload_b)


def test_generate_workload_changes_with_different_seed():
    workload_a = app.generate_workload(20, 5, 60, 42)
    workload_b = app.generate_workload(20, 5, 60, 43)

    assert not workload_a.equals(workload_b)


def test_generate_workload_minimum_valid_input_case():
    workload_df = app.generate_workload(1, 1, 10, 1)

    assert_workload_schema(workload_df, duration_minutes=10)


def test_generate_workload_high_load_case():
    workload_df = app.generate_workload(100, 30, 240, 42)

    assert_workload_schema(workload_df, duration_minutes=240)
    assert not workload_df.empty


def test_generate_workload_sparse_empty_generation_has_schema():
    workload_df = app.generate_workload(1, 1, 0, 1)

    assert workload_df.empty
    assert_workload_schema(workload_df, duration_minutes=0)
