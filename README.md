# Distributed Spark-Based Real-Time Drift Detection and Self-Healing ML System

End-to-end real-time ML pipeline for electricity load forecasting with drift detection and self-healing retraining.

## GitHub Repository

Organization: https://github.com/DataScience-ArtificialIntelligence

Repository URL: Add your final repository link here after creation in the above organization.

## Team Members

Institution: IIIT Dharwad, Dharwad, India

1. Muhammad Owais - 24bds045@iiitdw.ac.in
2. Ngamchingsen Willis Kipgen - 24bds047@iiitdw.ac.in
3. Ayman Pakkada - 24bds007@iiitdw.ac.in
4. Nitul Das - 24bds051@iiitdw.ac.in

Note: Equal contribution and equal marks policy as per course instruction.

## Project Overview

This project implements a production-style streaming ML system that:

1. Ingests power-load data streams.
2. Performs real-time inference using Spark Structured Streaming.
3. Tracks model quality via drift monitoring.
4. Triggers retraining and model promotion logic through a self-healing workflow.
5. Exposes outputs for analytics and frontend monitoring.

Core stack:

- Apache Kafka (stream transport)
- Apache Spark Structured Streaming (online serving)
- XGBoost (forecast model)
- Python (orchestration, drift checks, retraining)
- Next.js frontend dashboard (demo and monitoring UI)

## Architecture Diagram

![System Architecture](docs/assets/architecture-diagram.png)

See detailed design notes in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repository Structure

Main directories and purpose:

- src/: Core backend code (streaming, ML, drift detection, self-healing).
- frontend/: Next.js dashboard and demo UI.
- data/: Raw, processed, predictions, and metrics data.
- artifacts/: Models, baselines, drift reports, and self-healing outputs.
- checkpoints/: Producer and Spark streaming state.
- configs/: Project configuration files.
- tests/: Unit and integration test suite.
- scripts/: Utility, testing, and maintenance scripts.
- docs/: Architecture, reports, and project documentation.

## Installation and Implementation Process

### 1. Prerequisites

- Python 3.10+ (recommended)
- Java (required by Spark)
- Docker Desktop (for Kafka container)
- Node.js 18+ (for frontend)
- Git

### 2. Clone Repository

```bash
git clone <your-repo-url>
cd Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System
```

### 3. Create and Activate Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
& ".venv/Scripts/Activate.ps1"
```

Linux or WSL:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 5. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 6. Start Kafka

```powershell
docker run -p 9092:9092 apache/kafka:latest
```

## Executing the Code

Run each component in separate terminals.

### 1. Train Baseline Model (Offline)

```bash
python -m src.ml.train_baseline --log-level INFO
```

### 2. Start Data Producer

```bash
python -m src.streaming.kafka_producer --dataset "data/stream_dataset/hrl_load_metered-2019.csv" --sleep-seconds 0.1 --log-level INFO
```

### 3. Start Spark Streaming Inference

```bash
python -m src.streaming.spark_job --no-debug-mode --run-seconds 120
```

### 4. Run Drift Detection

```bash
python -m src.drift_detection.drift_detector
```

### 5. Run Self-Healing Trigger (Dry Run)

```bash
python -m src.self_healing.trigger --dry-run
```

### 6. Run Frontend Dashboard

```bash
cd frontend
npm run dev
```

Open http://localhost:3000 in browser.

## Key Output Locations

- Streaming predictions: data/predictions/
- Hourly metrics: data/metrics/hourly_metrics/
- Drift report: artifacts/drift/drift_report.json
- Model registry: artifacts/models/model_registry.jsonl
- Active model pointer: artifacts/models/active_model.json

## Testing

Run all tests:

```bash
pytest -q
```

Or use project helpers:

```bash
python run_tests.py
```

## 2-Minute Demo (Required)

Include a short demo video (around 2 minutes) that shows:

1. Project introduction and team names.
2. Kafka producer and Spark job running.
3. Live predictions and drift-monitoring behavior.
4. Frontend dashboard view.
5. Self-healing trigger/retraining flow (at least dry-run decision path).

Submission note: Mention the GitHub repository link in:

- Demo video
- Presentation slides
- Final report

## Collaboration Note

Anyone who wants to be added to the organization/repository should share their GitHub username with the repository owner so they can be invited as collaborator.
