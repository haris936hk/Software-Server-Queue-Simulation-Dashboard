import math
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import simpy
import streamlit as st


WORKLOAD_COLUMNS = [
    "request_id",
    "arrival_time_minutes",
    "service_time_minutes",
    "service_time_seconds",
]

REQUEST_COLUMNS = [
    "request_id",
    "arrival_time_minutes",
    "service_start_time_minutes",
    "completion_time_minutes",
    "waiting_time_seconds",
    "service_time_seconds",
    "response_time_seconds",
]

QUEUE_COLUMNS = ["time_minutes", "queue_length"]

DEFAULT_PARAMS = {
    "arrival_rate_per_minute": 20,
    "average_service_time_seconds": 5,
    "number_of_servers": 3,
    "simulation_duration_minutes": 60,
    "sla_threshold_seconds": 5,
    "random_seed": 42,
}

WORKLOAD_PRESETS = {
    "Healthy": {**DEFAULT_PARAMS},
    "Overloaded": {
        **DEFAULT_PARAMS,
        "arrival_rate_per_minute": 35,
        "number_of_servers": 2,
    },
    "Optimized": {
        **DEFAULT_PARAMS,
        "arrival_rate_per_minute": 35,
        "number_of_servers": 4,
    },
}


def generate_workload(
    arrival_rate_per_minute: int,
    average_service_time_seconds: int,
    simulation_duration_minutes: int,
    random_seed: int,
) -> pd.DataFrame:
    """Pre-generate one deterministic workload for fair scenario comparison."""
    rng = np.random.default_rng(random_seed)
    average_interarrival_minutes = 1 / arrival_rate_per_minute
    average_service_time_minutes = average_service_time_seconds / 60

    rows = []
    current_time = 0.0
    request_id = 1

    while True:
        current_time += float(rng.exponential(average_interarrival_minutes))
        if current_time > simulation_duration_minutes:
            break

        service_time_minutes = float(rng.exponential(average_service_time_minutes))
        rows.append(
            {
                "request_id": request_id,
                "arrival_time_minutes": current_time,
                "service_time_minutes": service_time_minutes,
                "service_time_seconds": service_time_minutes * 60,
            }
        )
        request_id += 1

    return pd.DataFrame(rows, columns=WORKLOAD_COLUMNS)


def empty_requests_df() -> pd.DataFrame:
    return pd.DataFrame(columns=REQUEST_COLUMNS)


def empty_queue_df(simulation_duration_minutes: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"time_minutes": 0.0, "queue_length": 0},
            {"time_minutes": float(simulation_duration_minutes), "queue_length": 0},
        ],
        columns=QUEUE_COLUMNS,
    )


def run_simulation(
    workload_df: pd.DataFrame,
    number_of_servers: int,
    simulation_duration_minutes: int,
) -> Tuple[pd.DataFrame, pd.DataFrame, float]:
    """Process a fixed workload through a SimPy server resource."""
    if workload_df.empty:
        observed_end_time_minutes = float(simulation_duration_minutes)
        return (
            empty_requests_df(),
            empty_queue_df(simulation_duration_minutes),
            observed_end_time_minutes,
        )

    env = simpy.Environment()
    server_pool = simpy.Resource(env, capacity=number_of_servers)
    completed_requests = []
    queue_records = [{"time_minutes": 0.0, "queue_length": 0}]

    def record_queue_length() -> None:
        time_minutes = float(env.now)
        queue_length = int(len(server_pool.queue))

        if queue_records and math.isclose(
            queue_records[-1]["time_minutes"], time_minutes, abs_tol=1e-10
        ):
            queue_records[-1]["queue_length"] = queue_length
        elif not queue_records or queue_records[-1]["queue_length"] != queue_length:
            queue_records.append(
                {"time_minutes": time_minutes, "queue_length": queue_length}
            )

    def request_lifecycle(request_row) -> None:
        arrival_time_minutes = float(request_row.arrival_time_minutes)
        service_time_minutes = float(request_row.service_time_minutes)

        if arrival_time_minutes > env.now:
            yield env.timeout(arrival_time_minutes - env.now)

        with server_pool.request() as server_request:
            record_queue_length()
            yield server_request

            service_start_time_minutes = float(env.now)
            record_queue_length()

            yield env.timeout(service_time_minutes)
            completion_time_minutes = float(env.now)

            waiting_time_minutes = service_start_time_minutes - arrival_time_minutes
            response_time_minutes = completion_time_minutes - arrival_time_minutes

            completed_requests.append(
                {
                    "request_id": int(request_row.request_id),
                    "arrival_time_minutes": arrival_time_minutes,
                    "service_start_time_minutes": service_start_time_minutes,
                    "completion_time_minutes": completion_time_minutes,
                    "waiting_time_seconds": waiting_time_minutes * 60,
                    "service_time_seconds": float(request_row.service_time_seconds),
                    "response_time_seconds": response_time_minutes * 60,
                }
            )

    sorted_workload = workload_df.sort_values("arrival_time_minutes")
    for request_row in sorted_workload.itertuples(index=False):
        env.process(request_lifecycle(request_row))

    env.run()

    requests_df = pd.DataFrame(completed_requests, columns=REQUEST_COLUMNS)
    final_completion_time = (
        float(requests_df["completion_time_minutes"].max())
        if not requests_df.empty
        else 0.0
    )
    observed_end_time_minutes = max(
        float(simulation_duration_minutes), final_completion_time
    )

    if queue_records[-1]["time_minutes"] < observed_end_time_minutes:
        queue_records.append(
            {
                "time_minutes": observed_end_time_minutes,
                "queue_length": queue_records[-1]["queue_length"],
            }
        )

    queue_df = pd.DataFrame(queue_records, columns=QUEUE_COLUMNS)
    return requests_df, queue_df, observed_end_time_minutes


def calculate_utilization(
    arrival_rate_per_minute: int,
    average_service_time_seconds: int,
    number_of_servers: int,
) -> float:
    service_rate_per_server = 60 / average_service_time_seconds
    return arrival_rate_per_minute / (number_of_servers * service_rate_per_server)


def calculate_time_weighted_average_queue_length(
    queue_df: pd.DataFrame,
    observed_end_time_minutes: float,
) -> float:
    if queue_df.empty or observed_end_time_minutes <= 0:
        return 0.0

    df = queue_df.copy()
    df = df.sort_values("time_minutes").drop_duplicates(
        subset=["time_minutes"], keep="last"
    )
    df = df[df["time_minutes"] <= observed_end_time_minutes]

    if df.empty:
        return 0.0

    if df.iloc[0]["time_minutes"] > 0:
        df = pd.concat(
            [
                pd.DataFrame([{"time_minutes": 0.0, "queue_length": 0}]),
                df,
            ],
            ignore_index=True,
        )

    if df.iloc[-1]["time_minutes"] < observed_end_time_minutes:
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "time_minutes": observed_end_time_minutes,
                            "queue_length": int(df.iloc[-1]["queue_length"]),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    next_times = df["time_minutes"].shift(-1)
    durations = (next_times - df["time_minutes"]).fillna(0).clip(lower=0)
    weighted_sum = (df["queue_length"] * durations).sum()

    return float(weighted_sum / observed_end_time_minutes)


def calculate_metrics(
    requests_df: pd.DataFrame,
    queue_df: pd.DataFrame,
    observed_end_time_minutes: float,
    arrival_rate_per_minute: int,
    average_service_time_seconds: int,
    number_of_servers: int,
    simulation_duration_minutes: int,
    sla_threshold_seconds: int,
) -> Dict[str, float]:
    completed_requests = int(len(requests_df))
    average_queue_length = calculate_time_weighted_average_queue_length(
        queue_df, observed_end_time_minutes
    )
    utilization = calculate_utilization(
        arrival_rate_per_minute,
        average_service_time_seconds,
        number_of_servers,
    )
    throughput = (
        completed_requests / simulation_duration_minutes
        if simulation_duration_minutes > 0
        else 0.0
    )

    if completed_requests == 0:
        return {
            "completed_requests": 0,
            "average_waiting_time_seconds": None,
            "average_response_time_seconds": None,
            "average_queue_length": average_queue_length,
            "server_utilization": utilization,
            "throughput": throughput,
            "sla_breach_rate": 0.0,
        }

    sla_breach_rate = float(
        (requests_df["response_time_seconds"] > sla_threshold_seconds).mean()
    )

    return {
        "completed_requests": completed_requests,
        "average_waiting_time_seconds": float(
            requests_df["waiting_time_seconds"].mean()
        ),
        "average_response_time_seconds": float(
            requests_df["response_time_seconds"].mean()
        ),
        "average_queue_length": average_queue_length,
        "server_utilization": utilization,
        "throughput": throughput,
        "sla_breach_rate": sla_breach_rate,
    }


def recommend_server_count(
    arrival_rate_per_minute: int,
    average_service_time_seconds: int,
    max_servers: int = 10,
    target_utilization: float = 0.85,
) -> Dict[str, float]:
    for server_count in range(1, max_servers + 1):
        utilization = calculate_utilization(
            arrival_rate_per_minute,
            average_service_time_seconds,
            server_count,
        )
        if utilization <= target_utilization:
            return {
                "recommended_servers": server_count,
                "recommended_utilization": utilization,
                "workload_may_still_be_too_high": False,
            }

    return {
        "recommended_servers": max_servers,
        "recommended_utilization": calculate_utilization(
            arrival_rate_per_minute,
            average_service_time_seconds,
            max_servers,
        ),
        "workload_may_still_be_too_high": True,
    }


def get_bottleneck_status(utilization: float) -> Tuple[str, str, str]:
    if utilization < 0.70:
        return (
            "Healthy / Possibly Over-Provisioned",
            "The system has enough capacity and may have spare resources.",
            "success",
        )
    if utilization < 0.85:
        return (
            "Good Utilization",
            "The system is using resources efficiently while keeping some safety margin.",
            "info",
        )
    if utilization < 1.00:
        return (
            "High Risk",
            "The system is close to full capacity. Small traffic spikes can cause long queues.",
            "warning",
        )
    return (
        "Overloaded",
        "Requests are arriving faster than the servers can process them. Queue length and response time are expected to grow.",
        "error",
    )


def format_seconds(value: float) -> str:
    return "N/A" if value is None else f"{value:.2f} sec"


def format_number(value: float) -> str:
    return "N/A" if value is None else f"{value:.2f}"


def format_percent(value: float, decimals: int = 1) -> str:
    return f"{value * 100:.{decimals}f}%"


def create_queue_length_chart(queue_df: pd.DataFrame) -> go.Figure:
    if queue_df.empty or not set(QUEUE_COLUMNS).issubset(queue_df.columns):
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=[],
                y=[],
                mode="lines",
                line={"shape": "hv", "width": 3},
                name="Queue length",
            )
        )
        fig.add_annotation(
            text="No queue data to display",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
        fig.update_layout(
            title="Queue Length Over Time",
            xaxis_title="Time (minutes)",
            yaxis_title="Queue length",
            margin=dict(l=20, r=20, t=60, b=20),
            height=430,
        )
        return fig

    fig = px.line(
        queue_df,
        x="time_minutes",
        y="queue_length",
        title="Queue Length Over Time",
        labels={
            "time_minutes": "Time (minutes)",
            "queue_length": "Queue length",
        },
        line_shape="hv",
        markers=True,
    )
    fig.update_traces(line=dict(width=3))
    fig.update_layout(margin=dict(l=20, r=20, t=60, b=20), height=430)
    return fig


def create_queue_chart(queue_df: pd.DataFrame) -> go.Figure:
    return create_queue_length_chart(queue_df)


def create_response_time_histogram(
    requests_df: pd.DataFrame,
    sla_threshold_seconds: int,
) -> go.Figure:
    if requests_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No completed requests to display",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
    else:
        fig = px.histogram(
            requests_df,
            x="response_time_seconds",
            nbins=30,
            title="Response Time Distribution",
            labels={
                "response_time_seconds": "Response time (seconds)",
                "count": "Number of requests",
            },
        )

    fig.add_vline(
        x=sla_threshold_seconds,
        line_width=3,
        line_dash="dash",
        line_color="red",
        annotation_text=f"SLA: {sla_threshold_seconds}s",
        annotation_position="top right",
    )
    fig.update_layout(
        yaxis_title="Number of requests",
        margin=dict(l=20, r=20, t=60, b=20),
        height=430,
    )
    return fig


def create_comparison_table(
    current_metrics: Dict[str, float],
    optimized_metrics: Dict[str, float],
    current_servers: int,
    optimized_servers: int,
) -> pd.DataFrame:
    rows = [
        {
            "Metric": "Average Waiting Time (sec)",
            f"Current ({current_servers} servers)": format_number(
                current_metrics["average_waiting_time_seconds"]
            ),
            f"Optimized ({optimized_servers} servers)": format_number(
                optimized_metrics["average_waiting_time_seconds"]
            ),
        },
        {
            "Metric": "Average Response Time (sec)",
            f"Current ({current_servers} servers)": format_number(
                current_metrics["average_response_time_seconds"]
            ),
            f"Optimized ({optimized_servers} servers)": format_number(
                optimized_metrics["average_response_time_seconds"]
            ),
        },
        {
            "Metric": "SLA Breach Rate (%)",
            f"Current ({current_servers} servers)": f"{current_metrics['sla_breach_rate'] * 100:.1f}",
            f"Optimized ({optimized_servers} servers)": f"{optimized_metrics['sla_breach_rate'] * 100:.1f}",
        },
        {
            "Metric": "Server Utilization (%)",
            f"Current ({current_servers} servers)": f"{current_metrics['server_utilization'] * 100:.1f}",
            f"Optimized ({optimized_servers} servers)": f"{optimized_metrics['server_utilization'] * 100:.1f}",
        },
    ]
    return pd.DataFrame(rows)


def create_comparison_bar_chart(
    current_metrics: Dict[str, float],
    optimized_metrics: Dict[str, float],
) -> go.Figure:
    chart_rows = [
        {
            "Metric": "Avg Waiting Time (sec)",
            "Scenario": "Current",
            "Value": current_metrics["average_waiting_time_seconds"] or 0.0,
        },
        {
            "Metric": "Avg Waiting Time (sec)",
            "Scenario": "Optimized",
            "Value": optimized_metrics["average_waiting_time_seconds"] or 0.0,
        },
        {
            "Metric": "Avg Response Time (sec)",
            "Scenario": "Current",
            "Value": current_metrics["average_response_time_seconds"] or 0.0,
        },
        {
            "Metric": "Avg Response Time (sec)",
            "Scenario": "Optimized",
            "Value": optimized_metrics["average_response_time_seconds"] or 0.0,
        },
        {
            "Metric": "SLA Breach Rate (%)",
            "Scenario": "Current",
            "Value": current_metrics["sla_breach_rate"] * 100,
        },
        {
            "Metric": "SLA Breach Rate (%)",
            "Scenario": "Optimized",
            "Value": optimized_metrics["sla_breach_rate"] * 100,
        },
        {
            "Metric": "Server Utilization (%)",
            "Scenario": "Current",
            "Value": current_metrics["server_utilization"] * 100,
        },
        {
            "Metric": "Server Utilization (%)",
            "Scenario": "Optimized",
            "Value": optimized_metrics["server_utilization"] * 100,
        },
    ]
    chart_df = pd.DataFrame(chart_rows)
    fig = px.bar(
        chart_df,
        x="Metric",
        y="Value",
        color="Scenario",
        barmode="group",
        title="Baseline vs Optimized Comparison",
        labels={"Value": "Value"},
    )
    fig.update_traces(texttemplate="%{y:.2f}", textposition="outside")
    fig.update_layout(margin=dict(l=20, r=20, t=60, b=20), height=460)
    return fig


def create_comparison_chart(
    current_metrics: Dict[str, float],
    optimized_metrics: Dict[str, float],
) -> go.Figure:
    return create_comparison_bar_chart(current_metrics, optimized_metrics)


def run_analysis(params: Dict[str, int]) -> Dict[str, object]:
    workload_df = generate_workload(
        params["arrival_rate_per_minute"],
        params["average_service_time_seconds"],
        params["simulation_duration_minutes"],
        params["random_seed"],
    )

    current_requests_df, current_queue_df, current_observed_end = run_simulation(
        workload_df,
        params["number_of_servers"],
        params["simulation_duration_minutes"],
    )
    current_metrics = calculate_metrics(
        current_requests_df,
        current_queue_df,
        current_observed_end,
        params["arrival_rate_per_minute"],
        params["average_service_time_seconds"],
        params["number_of_servers"],
        params["simulation_duration_minutes"],
        params["sla_threshold_seconds"],
    )

    recommendation = recommend_server_count(
        params["arrival_rate_per_minute"],
        params["average_service_time_seconds"],
    )
    optimized_servers = int(recommendation["recommended_servers"])
    optimized_requests_df, optimized_queue_df, optimized_observed_end = run_simulation(
        workload_df,
        optimized_servers,
        params["simulation_duration_minutes"],
    )
    optimized_metrics = calculate_metrics(
        optimized_requests_df,
        optimized_queue_df,
        optimized_observed_end,
        params["arrival_rate_per_minute"],
        params["average_service_time_seconds"],
        optimized_servers,
        params["simulation_duration_minutes"],
        params["sla_threshold_seconds"],
    )

    return {
        "workload_df": workload_df,
        "current_requests_df": current_requests_df,
        "current_queue_df": current_queue_df,
        "current_observed_end": current_observed_end,
        "current_metrics": current_metrics,
        "recommendation": recommendation,
        "optimized_requests_df": optimized_requests_df,
        "optimized_queue_df": optimized_queue_df,
        "optimized_observed_end": optimized_observed_end,
        "optimized_metrics": optimized_metrics,
    }


def render_metric_cards(metrics: Dict[str, float]) -> None:  # pragma: no cover
    top_cols = st.columns(4)
    top_cols[0].metric(
        "Completed Requests",
        f"{metrics['completed_requests']:,}",
        help="Total requests completed by the end of the observed simulation clock.",
    )
    top_cols[1].metric(
        "Average Waiting Time",
        format_seconds(metrics["average_waiting_time_seconds"]),
        help="Average time a request waits before service starts.",
    )
    top_cols[2].metric(
        "Average Response Time",
        format_seconds(metrics["average_response_time_seconds"]),
        help="Average waiting time plus service time.",
    )
    top_cols[3].metric(
        "Average Queue Length",
        f"{metrics['average_queue_length']:.2f}",
        help="Time-weighted average number of requests waiting in the queue.",
    )

    bottom_cols = st.columns(3)
    bottom_cols[0].metric(
        "Server Utilization",
        format_percent(metrics["server_utilization"]),
        help="Theoretical utilization based on arrival rate, service rate, and server count.",
    )
    bottom_cols[1].metric(
        "Throughput",
        f"{metrics['throughput']:.2f} req/min",
        help="Completed requests divided by selected simulation duration.",
    )
    bottom_cols[2].metric(
        "SLA Breach Rate",
        format_percent(metrics["sla_breach_rate"]),
        help="Completed requests with response time above the selected SLA threshold.",
    )


def render_bottleneck_detector(utilization: float) -> None:  # pragma: no cover
    status, explanation, level = get_bottleneck_status(utilization)
    message = f"**{status}** - Utilization is {format_percent(utilization)}. {explanation}"

    if level == "success":
        st.success(message)
    elif level == "info":
        st.info(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.error(message)


def render_autoscaling_panel(
    recommendation: Dict[str, float],
    current_servers: int,
    current_utilization: float,
) -> None:  # pragma: no cover
    recommended_servers = int(recommendation["recommended_servers"])
    recommended_utilization = float(recommendation["recommended_utilization"])
    explanation = (
        f"Recommended servers: **{recommended_servers}**. "
        f"The current configuration uses **{current_servers}** servers and has "
        f"**{format_percent(current_utilization)}** utilization. "
        f"With **{recommended_servers}** servers, utilization becomes "
        f"**{format_percent(recommended_utilization)}**."
    )

    if recommendation["workload_may_still_be_too_high"]:
        st.warning(
            explanation
            + " This is the maximum allowed in the demo, and the workload may still be too high."
        )
    else:
        st.info(explanation + " This is within the target range of 85% or lower.")


def render_event_log(requests_df: pd.DataFrame) -> None:  # pragma: no cover
    st.subheader("Request Event Log")

    if requests_df.empty:
        st.info("No completed requests were recorded for this scenario.")
        return

    event_log_df = requests_df[REQUEST_COLUMNS].head(50).copy()
    numeric_columns = [column for column in REQUEST_COLUMNS if column != "request_id"]
    event_log_df[numeric_columns] = event_log_df[numeric_columns].round(2)
    st.dataframe(event_log_df, use_container_width=True, hide_index=True)


def render_interpretation_section() -> None:  # pragma: no cover
    st.subheader("How to Interpret This Simulation")
    st.markdown(
        """
- **Arrival rate:** Higher arrival rate means more requests enter the system per minute.
- **Service time:** Higher service time means each request takes longer to process.
- **Number of servers:** More servers increase system capacity and usually reduce waiting time.
- **Utilization:** Utilization shows how busy the servers are. Very high utilization can cause long queues.
- **Queue length:** A growing queue means the system cannot keep up with demand.
- **SLA breach rate:** This is the percentage of requests whose response time is above the selected SLA threshold.
- **Baseline vs optimized:** This comparison shows whether adding more server workers improves performance.
"""
    )


def main() -> None:  # pragma: no cover
    st.set_page_config(
        page_title="Software Server Queue Simulation Dashboard",
        page_icon="",
        layout="wide",
    )

    if "active_params" not in st.session_state:
        st.session_state.active_params = DEFAULT_PARAMS.copy()

    for name, value in st.session_state.active_params.items():
        st.session_state.setdefault(f"control_{name}", value)

    def apply_workload_preset() -> None:
        preset = st.session_state.workload_preset
        if preset is not None:
            for name, value in WORKLOAD_PRESETS[preset].items():
                st.session_state[f"control_{name}"] = value

    st.sidebar.title("Simulation Controls")
    st.sidebar.selectbox(
        "Quick workload preset",
        options=list(WORKLOAD_PRESETS),
        index=None,
        placeholder="Choose a workload…",
        key="workload_preset",
        on_change=apply_workload_preset,
    )
    st.sidebar.caption(
        "Presets fill the controls below, including seed 42. "
        "Adjust any value, then click Run Simulation to apply."
    )
    with st.sidebar.form("simulation_controls"):
        arrival_rate_per_minute = st.slider(
            "Arrival Rate (requests per minute)",
            min_value=1,
            max_value=100,
            key="control_arrival_rate_per_minute",
            step=1,
        )
        average_service_time_seconds = st.slider(
            "Average Service Time (seconds per request)",
            min_value=1,
            max_value=30,
            key="control_average_service_time_seconds",
            step=1,
        )
        number_of_servers = st.slider(
            "Number of Server Workers",
            min_value=1,
            max_value=10,
            key="control_number_of_servers",
            step=1,
        )
        simulation_duration_minutes = st.slider(
            "Simulation Duration (minutes)",
            min_value=10,
            max_value=240,
            key="control_simulation_duration_minutes",
            step=10,
        )
        sla_threshold_seconds = st.slider(
            "SLA Threshold (seconds)",
            min_value=1,
            max_value=60,
            key="control_sla_threshold_seconds",
            step=1,
        )
        random_seed = st.number_input(
            "Random Seed",
            min_value=1,
            max_value=99999,
            key="control_random_seed",
            step=1,
        )
        run_clicked = st.form_submit_button("Run Simulation", type="primary")

    if run_clicked:
        st.session_state.active_params = {
            "arrival_rate_per_minute": int(arrival_rate_per_minute),
            "average_service_time_seconds": int(average_service_time_seconds),
            "number_of_servers": int(number_of_servers),
            "simulation_duration_minutes": int(simulation_duration_minutes),
            "sla_threshold_seconds": int(sla_threshold_seconds),
            "random_seed": int(random_seed),
        }

    params = st.session_state.active_params

    st.title("Software Server Queue Simulation Dashboard")
    st.write(
        "This demo simulates incoming software/API requests waiting for backend server workers. "
        "It shows how λ / arrival rate, average service time, and c / number of servers affect "
        "queue length, waiting time, response time, utilization, throughput, and SLA breaches."
    )
    st.code(
        "Incoming Requests -> Waiting Queue -> Server Workers -> Completed Responses",
        language="text",
    )

    analysis = run_analysis(params)
    current_metrics = analysis["current_metrics"]
    optimized_metrics = analysis["optimized_metrics"]
    recommendation = analysis["recommendation"]

    st.caption(
        "Current run: "
        f"{params['arrival_rate_per_minute']} requests/min, "
        f"{params['average_service_time_seconds']} sec average service time, "
        f"{params['number_of_servers']} server workers, "
        f"{params['simulation_duration_minutes']} minutes, "
        f"{params['sla_threshold_seconds']} sec SLA, "
        f"seed {params['random_seed']}."
    )

    st.subheader("KPI Metrics")
    render_metric_cards(current_metrics)

    st.subheader("Bottleneck Detector")
    render_bottleneck_detector(current_metrics["server_utilization"])

    st.subheader("Auto-Scaling Recommendation")
    render_autoscaling_panel(
        recommendation,
        params["number_of_servers"],
        current_metrics["server_utilization"],
    )

    st.subheader("Queue Length Over Time")
    st.plotly_chart(
        create_queue_length_chart(analysis["current_queue_df"]),
        use_container_width=True,
    )

    st.subheader("Response Time Distribution")
    st.plotly_chart(
        create_response_time_histogram(
            analysis["current_requests_df"],
            params["sla_threshold_seconds"],
        ),
        use_container_width=True,
    )

    st.subheader("Baseline vs Optimized Comparison")
    optimized_servers = int(recommendation["recommended_servers"])
    comparison_table = create_comparison_table(
        current_metrics,
        optimized_metrics,
        params["number_of_servers"],
        optimized_servers,
    )
    st.dataframe(comparison_table, use_container_width=True, hide_index=True)
    st.plotly_chart(
        create_comparison_bar_chart(current_metrics, optimized_metrics),
        use_container_width=True,
    )

    render_event_log(analysis["current_requests_df"])
    render_interpretation_section()


if __name__ == "__main__":  # pragma: no cover
    main()
