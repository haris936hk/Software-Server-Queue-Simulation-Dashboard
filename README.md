# Software Server Queue Simulation Dashboard

## Project Topic

Queueing Models for Software Systems

## Description

This project is a Streamlit web application that simulates incoming software/API requests waiting for backend server workers. It demonstrates how arrival rate, average service time, and number of parallel server workers affect queue length, waiting time, response time, throughput, utilization, and SLA breaches.

The dashboard is self-contained after dependencies are installed. It does not require external APIs, databases, cloud services, authentication, or internet access.

## Features

- Interactive Streamlit dashboard
- SimPy-based discrete-event simulation
- Adjustable arrival rate, service time, servers, duration, SLA threshold, and random seed
- KPI metrics
- Queue length over time chart
- Response time distribution chart
- Bottleneck detector
- Auto-scaling recommendation
- Baseline vs optimized comparison
- Request event log

## How the Model Works

The simulated system follows this flow:

```text
Incoming Requests -> Waiting Queue -> Server Workers -> Completed Responses
```

Requests arrive randomly over time. If all server workers are busy, a request waits in the queue. Each server worker processes one request at a time. After service is complete, the request leaves the system as a completed response.

The simulation records:

- Waiting time before service starts
- Service time
- Response time
- Queue length changes over time
- Throughput
- SLA breaches

The workload is generated once using the selected random seed. The same request IDs, arrival times, and service times are reused for both the baseline and optimized scenarios, so the comparison mainly reflects the effect of changing the number of server workers.

The simulation stops generating new arrivals after the selected simulation duration. Requests that already arrived are allowed to finish, so the observed simulation clock may extend past the selected duration when the system is heavily loaded.

Average queue length is calculated as a time-weighted average:

```text
average_queue_length = sum(queue_length * duration_at_that_length) / total_observed_time
```

## Queueing Theory Connection

This project represents an M/M/c-style queue:

- λ / arrival rate: requests arriving per minute
- μ / service rate: requests processed per minute by one server
- c / number of servers: number of parallel backend workers
- Utilization: how busy the system is
- Queue length: number of requests waiting
- Waiting time: time spent waiting before service starts
- Response time: waiting time + service time
- SLA threshold: maximum acceptable response time

The utilization formula used in the dashboard is:

```text
utilization = λ / (c × μ)
```

In this app:

```text
μ = 60 / average_service_time_seconds
```

## How to Run

1. Create and activate a virtual environment.

   Windows PowerShell:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   macOS/Linux:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies.

   ```bash
   pip install -r requirements.txt
   ```

3. Run the app.

   ```bash
   streamlit run app.py
   ```

## Suggested Demo Scenarios

Use **Quick workload preset** at the top of the sidebar to load **Healthy**,
**Overloaded**, or **Optimized**, matching the scenarios below. Each preset also
sets the random seed to 42 for reproducible comparisons. Presets only fill the
controls; adjust any values and click **Run Simulation** to update the results.
The existing results stay visible until you submit.

### Scenario 1: Healthy System

- Arrival rate: 20 requests/min
- Average service time: 5 seconds
- Servers: 3
- Duration: 60 minutes
- SLA threshold: 5 seconds

### Scenario 2: Overloaded System

- Arrival rate: 35 requests/min
- Average service time: 5 seconds
- Servers: 2
- Duration: 60 minutes
- SLA threshold: 5 seconds

### Scenario 3: Optimized System

- Arrival rate: 35 requests/min
- Average service time: 5 seconds
- Servers: 4
- Duration: 60 minutes
- SLA threshold: 5 seconds

## Limitations

- The model is a simplified simulation.
- It assumes random exponential arrivals and service times.
- It does not model real network latency, database locks, caching, failures, or multiple request classes.
- It is designed for educational simulation and modeling purposes.
