import importlib


def test_app_imports_successfully():
    module = importlib.import_module("app")

    assert module is not None


def test_required_functions_exist():
    import app

    required_functions = [
        "generate_workload",
        "run_simulation",
        "calculate_utilization",
        "recommend_server_count",
        "calculate_metrics",
        "create_queue_chart",
        "create_response_time_histogram",
        "create_comparison_chart",
        "get_bottleneck_status",
    ]

    for function_name in required_functions:
        assert hasattr(app, function_name)
        assert callable(getattr(app, function_name))


def test_main_entrypoint_exists():
    import app

    assert hasattr(app, "main")
    assert callable(app.main)


def test_run_analysis_returns_expected_sections():
    import app

    analysis = app.run_analysis(app.DEFAULT_PARAMS.copy())

    expected_keys = {
        "workload_df",
        "current_requests_df",
        "current_queue_df",
        "current_observed_end",
        "current_metrics",
        "recommendation",
        "optimized_requests_df",
        "optimized_queue_df",
        "optimized_observed_end",
        "optimized_metrics",
    }
    assert set(analysis) == expected_keys
    assert analysis["current_metrics"]["completed_requests"] == len(
        analysis["current_requests_df"]
    )
