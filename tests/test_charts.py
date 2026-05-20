import pandas as pd
import plotly.graph_objects as go

import app


def sample_metrics():
    return {
        "completed_requests": 2,
        "average_waiting_time_seconds": 2.0,
        "average_response_time_seconds": 6.0,
        "average_queue_length": 1.0,
        "server_utilization": 0.75,
        "throughput": 0.2,
        "sla_breach_rate": 0.5,
    }


def optimized_metrics():
    metrics = sample_metrics()
    metrics.update(
        {
            "average_waiting_time_seconds": 1.0,
            "average_response_time_seconds": 5.0,
            "server_utilization": 0.50,
            "sla_breach_rate": 0.25,
        }
    )
    return metrics


def test_queue_chart_returns_step_line_figure():
    queue_df = pd.DataFrame(
        {"time_minutes": [0, 2, 5], "queue_length": [0, 3, 1]},
        columns=app.QUEUE_COLUMNS,
    )

    fig = app.create_queue_chart(queue_df)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    assert fig.data[0].type == "scatter"
    assert fig.data[0].line.shape == "hv"
    assert list(fig.data[0].x) == [0, 2, 5]
    assert list(fig.data[0].y) == [0, 3, 1]


def test_response_time_histogram_contains_histogram_and_sla_line():
    requests_df = pd.DataFrame(
        {
            "response_time_seconds": [1, 2, 3, 6, 8],
        }
    )

    fig = app.create_response_time_histogram(requests_df, sla_threshold_seconds=5)

    assert isinstance(fig, go.Figure)
    assert any(trace.type == "histogram" for trace in fig.data)
    assert fig.layout.shapes
    assert any(shape.x0 == 5 and shape.x1 == 5 for shape in fig.layout.shapes)


def test_comparison_chart_contains_scenarios_and_required_metrics():
    fig = app.create_comparison_chart(sample_metrics(), optimized_metrics())

    assert isinstance(fig, go.Figure)
    assert {trace.name for trace in fig.data} == {"Current", "Optimized"}

    metric_labels = set()
    for trace in fig.data:
        metric_labels.update(str(label) for label in trace.x)

    assert any("Waiting Time" in label for label in metric_labels)
    assert any("Response Time" in label for label in metric_labels)
    assert any("SLA Breach Rate" in label for label in metric_labels)
    assert any("Server Utilization" in label for label in metric_labels)


def test_comparison_table_contains_required_metrics():
    table = app.create_comparison_table(sample_metrics(), optimized_metrics(), 2, 4)

    assert list(table["Metric"]) == [
        "Average Waiting Time (sec)",
        "Average Response Time (sec)",
        "SLA Breach Rate (%)",
        "Server Utilization (%)",
    ]
    assert "Current (2 servers)" in table.columns
    assert "Optimized (4 servers)" in table.columns


def test_empty_request_data_histogram_is_display_safe():
    fig = app.create_response_time_histogram(pd.DataFrame(), sla_threshold_seconds=5)

    assert isinstance(fig, go.Figure)
    assert fig.layout.shapes


def test_empty_queue_chart_is_display_safe():
    fig = app.create_queue_chart(pd.DataFrame())

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert fig.data[0].line.shape == "hv"
