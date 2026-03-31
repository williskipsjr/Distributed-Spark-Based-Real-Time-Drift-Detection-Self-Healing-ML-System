# End-to-End Pipeline Test Guide

**Last Updated:** March 31, 2026  
**Status:** SYSTEM COMPLETE - Multi-dataset cycling, automated self-healing, full orchestration  
**Test Duration:** ~30-45 minutes from reset to full automation cycle

---

## COMPLETE SYSTEM OVERVIEW

This fully automated self-healing ML system includes:

### The 4 Core Components (All Implemented)
1. **Kafka Broker** — Apache Kafka message broker
2. **Kafka Producer** — Streams CSV data, AUTO-CYCLES through 2020→2021→2022 datasets
3. **Spark Streaming Job** — Real-time predictions + hourly metrics aggregation
4. **Self-Healing Orchestrator** — Auto detects drift → triggers retrain → promotes models

### The Complete Flow
```
Kafka Producer (2020.csv)
    ↓ (streams records every 0.1s)
Kafka Broker (pjm.load topic)
    ↓
Spark Job (reads, predicts, aggregates)
    ↓
Hourly Metrics (data/metrics/hourly_metrics/*.parquet)
    ↓
Orchestrator (checks every 60s)
    ├→ Drift Detection (KS test, PSI test)
    ├→ Trigger Policy (3 consecutive drifts threshold)
    ├→ Auto Retrain (if threshold met)
    └→ Auto Promote (if candidate better)
```

---

## PREREQUISITE CHECK

Before starting, verify these datasets exist:

```powershell
# From project root directory:
Test-Path "data/stream_dataset/hrl_load_metered-2020.csv"  # Should be True
Test-Path "data/stream_dataset/hrl_load_metered-2021.csv"  # Should be True
Test-Path "data/stream_dataset/hrl_load_metered-2022.csv"  # Should be False (optional)
```

---

## STEP 0: SYSTEM CLEANUP (REQUIRED - Run Once)

**Run this FIRST before starting any terminals:**

```powershell
# Navigate to project root
cd "c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"

# Activate venv if not already active
& "..\..\..\..\..\..\.venv\Scripts\Activate.ps1"

# Clear ALL previous pipeline state
python reset_pipeline.py --hard-reset
```

**What gets cleared:**
- ✓ Kafka producer resume state (`checkpoints/producer/producer_state.json`)
- ✓ Spark checkpoints (`checkpoints/spark_predictions/`) - forces re-read from Kafka latest
- ✓ Hourly metrics (`data/metrics/hourly_metrics/`)
- ✓ Prediction files (`data/predictions/`)
- ✓ Drift history (`artifacts/drift/drift_history.jsonl`)
- ✓ Drift monitor state (`artifacts/drift/drift_monitor_state.json`)
- ✓ Orchestrator decisions (`artifacts/self_healing/trigger_decisions.jsonl`)

**What is preserved:**
- ✓ Base model (`artifacts/models/model_v1.joblib`)
- ✓ Baseline metrics (`artifacts/baselines/`)
- ✓ Raw data (`data/raw/`, `data/stream_dataset/`)
- ✓ Configuration (`configs/`)

**Expected output:**
```
Resetting pipeline state...
Deleted hourly metrics from data/metrics/hourly_metrics (X items)
Deleted Spark checkpoints from checkpoints/spark_predictions (X items)
Deleted prediction outputs from data/predictions (X items)
Deleted drift reports from artifacts/drift (X items)
Pipeline state reset complete.
```

---

## STEP 1: KAFKA BROKER (Terminal 1)

**Purpose:** Message broker for streaming data

**Choice A - Using Docker (Preferred if Docker is available):**
```powershell
docker run --rm -p 9092:9092 -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 apache/kafka:latest
```

**Choice B - Using Local Kafka (If Docker not available):**
```powershell
# From Kafka installation directory
.\bin\windows\kafka-server-start.bat .\config\server.properties
```

**Expected output:**
```
[KafkaServer id=0] started (kafka.server.KafkaServer)
```

**Validation:** Open new terminal and run:
```powershell
netstat -ano | findstr :9092
# Should show: TCP 127.0.0.1:9092 0.0.0.0:* LISTENING
```

---

## STEP 2: SPARK STREAMING JOB (Terminal 2)

**Purpose:** Consumes Kafka messages, runs predictions, writes hourly metrics  
**Start:** After Broker is listening on port 9092 (5+ seconds)

If running Spark from WSL/bash, export Python interpreter variables first:

```bash
export PYSPARK_PYTHON="$(which python)"
export PYSPARK_DRIVER_PYTHON="$(which python)"
```

```powershell
cd "c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"

& "..\..\..\..\..\..\.venv\Scripts\Activate.ps1"

python -m src.streaming.spark_job `
  --checkpoint-path "checkpoints/spark_predictions" `
  --output-path "data/metrics" `
  --log-level INFO
```

**Expected output:**
```
[INFO] spark-session-created: master=local[1], app_name=pjm-load-streaming
[INFO] kafka-bootstrap-servers: localhost:9092
[INFO] kafka-topic: pjm.load
[INFO] model-loaded: version=model_v1, path=artifacts/models/model_v1.joblib
[INFO] Starting new Spark query: kafka-to-metrics
[INFO] query-started: id=..., status=ACTIVE
[INFO] Batch 0: 0 rows (waiting for Kafka messages)
```

**Validation:** 
- Spark UI appears at http://localhost:4040
- Look for "pjm-load-streaming" application
- No error messages in logs

---

## STEP 3: KAFKA PRODUCER (Terminal 3)

**Purpose:** Streams historical load data, AUTO-CYCLES through 2020→2021 datasets  
**Start:** After Spark job is running (10+ seconds)

```powershell
cd "c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"

& "..\..\..\..\..\..\.venv\Scripts\Activate.ps1"

python -m src.streaming.kafka_producer `
  --dataset "data/stream_dataset/hrl_load_metered-2020.csv" `
  --sleep-seconds 0.1 `
  --resume `
  --reset-state `
  --log-level INFO
```

**Parameters explained:**
- `--dataset` — Starting dataset (auto-cycles to 2021, 2022 when done)
- `--sleep-seconds 0.1` — Delay between records (speeds up test)
- `--resume` — Saves state to allow resuming if interrupted
- `--reset-state` — Forces fresh start (ignores any previous resume state)

**Expected output (First 30 seconds):**
```
[INFO] producer-start: dataset_sequence=[
  'data/stream_dataset/hrl_load_metered-2020.csv',
  'data/stream_dataset/hrl_load_metered-2021.csv'
], dataset_index=0, dataset_count=2, rows=8760
[INFO] Starting publication loop...
[INFO] record-published: timestamp=2020-01-01T01:00:00, load_mw=150234.5
[INFO] record-published: timestamp=2020-01-01T02:00:00, load_mw=148921.3
[INFO] record-published: timestamp=2020-01-01T03:00:00, load_mw=145621.8
...
[INFO] published_total: 100 records

# After ~2 hours of streaming (8760 records / 0.1s per record):
[INFO] producer-dataset-switch: dataset_index=1, dataset_path=...2021.csv, rows=8784
[INFO] record-published: timestamp=2021-01-01T01:00:00, load_mw=152100.2
```

**What's happening:**
- Producer loads 2020.csv (8,760 hourly records)
- Streams at 0.1s per record = ~15 minutes to complete 2020
- Auto-switches to 2021.csv when 2020 is done
- Both loaded into Kafka topic `pjm.load`
- Spark job is consuming and aggregating in real-time

---

## STEP 4: WAIT FOR METRICS TO ACCUMULATE

**Duration:** Let producer+spark run together for **5-10 minutes minimum**

**Monitor metrics production** (optional, in separate terminal):
```powershell
# Check how many hourly metric files exist
Get-ChildItem -Path "data/metrics/hourly_metrics" -Recurse -File | Measure-Object

# Get detailed info
Get-ChildItem -Path "data/metrics/hourly_metrics" -Recurse -File | Select-Object Name, Length

# Watch it grow in real-time
Watch-Item -Path "data/metrics/hourly_metrics" -Action Created
```

**Expected progress:**
- T+5 min: ~300 hourly metric files
- T+10 min: ~600 hourly metric files
- T+15 min: ~900 hourly metric files

**Check Spark UI** at http://localhost:4040:
- View "Active Jobs" — should show "pjm-load-streaming"
- View "Completed Stages" — growing number of micro-batches
- View "Structured Streaming" tab — query stats, rates

---

## STEP 5: START ORCHESTRATOR (Terminal 4)

**Purpose:** Continuously monitors drift, auto-triggers retrain, auto-promotes models  
**Start:** After at least 5 minutes of metrics accumulation

```powershell
cd "c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"

& "..\..\..\..\..\..\.venv\Scripts\Activate.ps1"

python -m src.self_healing.orchestrator `
  --interval-seconds 60 `
  --max-runs 30 `
  --required-consecutive-drifts 3 `
  --cooldown-minutes 10 `
  --stream-csv-path "data/stream_dataset/hrl_load_metered-2021.csv" `
  --recent-days 30 `
  --min-relative-improvement 0.02 `
  --log-level INFO
```

**Parameters explained:**
- `--interval-seconds 60` — Check for drift every 60 seconds
- `--max-runs 30` — Stop after 30 checks (~30 minutes), let it finish for full test
- `--required-consecutive-drifts 3` — Require 3 consecutive drift detections before triggering retrain
- `--cooldown-minutes 10` — Wait 10 minutes between retrains (test mode; prod would be 180)
- `--stream-csv-path` — Dataset for retraining window
- `--recent-days 30` — Use last 30 days of data for retrain
- `--min-relative-improvement 0.02` — Candidate must improve MAE by ≥2% to promote

**Expected output (First orchestrator check):**
```
[INFO] orchestrator-started: interval_seconds=60, max_runs=30, required_consecutive_drifts=3
[INFO] orchestrator-step-complete: drift_detected=False, trigger_decision=no_action
[INFO] orchestrator-step-complete: drift_detected=False, trigger_decision=no_action
[INFO] orchestrator-step-complete: drift_detected=True, trigger_decision=no_action (waiting for threshold: 1/3)
[INFO] orchestrator-step-complete: drift_detected=True, trigger_decision=no_action (waiting for threshold: 2/3)
[INFO] orchestrator-step-complete: drift_detected=True, trigger_decision=retrain_candidate, threshold=3/3
[INFO] orchestrator-retrain-triggered: trigger_reason=persistent drift detected (3 consecutive checks >= 3)

# Retrain starts (takes 1-3 minutes depending on data)
[INFO] retrain-pipeline-started: candidate_version=candidate_20260331T123456Z
[INFO] training-complete: candidate_version=candidate_20260331T123456Z, mae=8234.5
[INFO] promotion-recommended: candidate_mae=8234.5 < current_mae=8945.2 (improvement=8.0%)

# Promotion happens next no-drift check
[INFO] orchestrator-step-complete: drift_detected=False, trigger_decision=promote_candidate
[INFO] orchestrator-promotion-triggered: trigger_reason=candidate_better than current
[INFO] orchestrator-promotion-complete: decision=promote, reason=all promotion gates passed
[INFO] model-pointer-updated: active_model -> candidate_20260331T123456Z
```

---

## MONITORING DASHBOARD (Optional - 5 Additional Terminals)

While tests run, open these to monitor different aspects:

### Monitor 1: Kafka Messages Being Published
```powershell
# Count records in partition 0
cd "c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"

# Check offset (if Kafka CLI available)
kafka-consumer-groups --bootstrap-servers localhost:9092 --group spark-kafka --describe
```

### Monitor 2: Metrics File Count (Real-time)
```powershell
$path = "data/metrics/hourly_metrics"
while($true) {
    $count = (Get-ChildItem -Path $path -Recurse -File -ErrorAction SilentlyContinue).Count
    Write-Host "$(Get-Date): $count metric files"
    Start-Sleep -Seconds 10
}
```

### Monitor 3: Orchestrator Decisions (Live Follow)
```powershell
$path = "artifacts/self_healing/trigger_decisions.jsonl"
Get-Content -Path $path -Tail 5 -Wait | ConvertFrom-Json | Format-Table decision_time_utc, drift_detected, trigger_decision, action_executed
```

### Monitor 4: Candidate Report Changes
```powershell
$path = "artifacts/models/candidate_report.json"
while($true) {
    if (Test-Path $path) {
        $report = Get-Content $path | ConvertFrom-Json
        Write-Host "$(Get-Date): Candidate exists"
        Write-Host "  MAE: $($report.current_metrics.mae) (current) → $($report.candidate_metrics.mae) (candidate)"
    } else {
        Write-Host "$(Get-Date): No candidate report yet"
    }
    Start-Sleep -Seconds 5
}
```

### Monitor 5: Active Model Pointer
```powershell
while($true) {
    if (Test-Path "artifacts/models/active_model.json") {
        $active = Get-Content "artifacts/models/active_model.json" | ConvertFrom-Json
        Write-Host "$(Get-Date): Active Model: $($active.version)"
    }
    Start-Sleep -Seconds 10
}
```

---

## EXPECTED TIMELINE

| Time | Event |
|------|-------|
| T+0s | Reset pipeline state ✓ |
| T+1m | Broker starts listening on 9092 ✓ |
| T+6s | Spark job starts, waiting for messages |
| T+16s | Producer starts streaming 2020 data |
| T+30s | First Kafka messages in broker topic |
| T+60s | Spark writes first hourly metrics |
| T+2m | ~300 hourly metric files in place |
| T+5m | **Start orchestrator** |
| T+6m | Orchestrator starts drift checks (first check) |
| T+7m | Drift detection (check #2) |
| T+8m | Drift detection (check #3 - threshold met!) |
| T+9m-12m | **Retrain pipeline runs** (candidate model training) |
| T+13m | Promotion check (if candidate better, promote) |
| T+14m+ | **Active model updated** to new candidate |
| T+22m | Producer finishes 2020.csv, auto-switches to 2021.csv |
| T+25m-45m | Orchestrator continues checking, possible more drifts |

---

## SUCCESS CRITERIA

All conditions must be TRUE:

- [ ] **Broker:** Terminal 1 shows `[KafkaServer id=0] started`
- [ ] **Spark Job:** Terminal 2 shows `query-started: status=ACTIVE` with increasing batch counts
- [ ] **Producer:** Terminal 3 shows `record-published` increasing every second
- [ ] **Producer Dataset Switch:** Logs show `producer-dataset-switch` from 2020→2021
- [ ] **Metrics:** `data/metrics/hourly_metrics/` contains 600+ parquet files
- [ ] **Orchestrator:** Terminal 4 shows `orchestrator-started`
- [ ] **Drift Detected:** At least one `drift_detected=True` in logs
- [ ] **Retrain Triggered:** Orchestrator prints `orchestrator-retrain-triggered` message
- [ ] **Retrain Complete:** Orchestrator prints `orchestrator-retrain-complete` with candidate version
- [ ] **Candidate Report:** File `artifacts/models/candidate_report.json` exists
- [ ] **Promotion:** Orchestrator prints `orchestrator-promotion-complete` OR `decision=promote`
- [ ] **Decision Log:** `artifacts/self_healing/trigger_decisions.jsonl` has 30+ lines with varied `trigger_decision` values
- [ ] **No Errors:** No ERROR or EXCEPTION messages in any terminal

---

## TROUBLESHOOTING

### Producer stuck after 2020 dataset
**Problem:** Logs show `producer-complete` before reaching 2021  
**Solution:** Check `--loop-forever` flag — should default to true. If missing, producer auto-cycles anyway via dataset_sequence.

### Orchestrator not detecting drift
**Problem:** All checks show `drift_detected=False`  
**Solution:** 
- Need at least 7 days baseline + 24 hours recent data
- Current dataset may not differ enough from baseline
- Check that baseline metrics exist in `artifacts/baselines/`

### Spark job not writing metrics
**Problem:** `data/metrics/hourly_metrics/` stays empty  
**Solution:**
- Check Kafka broker is running on 9092
- Check producer is publishing messages (terminal 3 shows `record-published`)
- Check Spark logs for connection errors
- Verify checkpoint directory exists and is writable

### "Can't connect to Kafka" error
**Problem:** Producer/Spark show connection refused on localhost:9092  
**Solution:**
- Verify broker terminal shows it's listening
- Try `netstat -ano | findstr :9092`
- If using Docker, verify Docker daemon is running
- Restart broker and wait 5 seconds before retry

---

## CLEANUP AFTER TEST

**To stop everything gracefully:**

1. **Stop Producer** (Ctrl+C in Terminal 3)
   - Saves resume state (can resume later with `--resume`)

2. **Stop Spark Job** (Ctrl+C in Terminal 2)
   - Preserves checkpoints by default (restart picks up where it left off)

3. **Stop Orchestrator** (Ctrl+C in Terminal 4)
   - Logs all decisions before stopping

4. **Stop Broker** (Ctrl+C in Terminal 1)
   - Saves all topics and offsets

**For full cleanup before next test run:**
```powershell
python reset_pipeline.py --hard-reset
```

---

## NEXT STEPS AFTER SUCCESS

Once this end-to-end test passes:

1. **Increase cooldown** — Change `--cooldown-minutes 10` → `180` for production
2. **Increase interval** — Change `--interval-seconds 60` → `300` for lower CPU
3. **Add more datasets** — Create 2022, 2023 CSV files in `data/stream_dataset/`
4. **Configure thresholds** — Adjust `--required-consecutive-drifts`, `--recent-days`, `--min-relative-improvement`
5. **Monitor logs** — Set up logging aggregation for production
6. **Archive results** — Save `artifacts/` and decision logs for analysis

---

## PROJECT STATUS: ✅ COMPLETE

✓ Multi-year dataset auto-cycling: 2020 → 2021 → loop  
✓ Fully automated orchestration: No manual triggers needed  
✓ Drift detection: KS test + PSI test implemented  
✓ Guardrail evaluation: Automatic threshold checking  
✓ Auto-retrain: Invoked on persistent drift  
✓ Auto-promotion: Model promoted when candidate better  
✓ State management: Checkpoints, resume capability, decision logs  
✓ Monitoring: Structured logging, JSONL decision history  

**This is a production-ready self-healing ML pipeline.**

## CLEANUP

Stop all terminals with Ctrl+C in order:
1. Terminal 4 (Orchestrator) - Ctrl+C
2. Terminal 3 (Producer) - Ctrl+C  
3. Terminal 2 (Spark Job) - Ctrl+C
4. Terminal 1 (Broker) - Ctrl+C

Then:
```powershell
docker stop $(docker ps -q)  # Stop all containers
```

---

## TROUBLESHOOTING

**Issue:** Orchestrator says "No metrics found"
→ Wait longer for metrics to accumulate; metrics only created after Spark processes data

**Issue:** Producer not sending data
→ Check Kafka broker is running at localhost:9092
→ Verify dataset path exists

**Issue:** Spark job not creating metrics
→ Check Spark logs for errors
→ Verify producer is publishing to correct topic (pjm.load)

**Issue:** "Consecutive drift threshold not met"
→ Normal! Orchestrator waits for 3+ consecutive drift detections
→ This prevents false positives

---

## AUTOMATIC DATA ROLLOVER

Note: Producer automatically advances from 2020 → 2021 datasets once 2020 is exhausted. You don't need to restart it.

To include 2022 in the sequence, add the CSV file to `data/stream_dataset/` directory with the naming pattern `hrl_load_metered-20XX.csv`.
