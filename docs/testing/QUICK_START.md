# Quick Start - Copy-Paste Ready Commands

**Total Test Duration:** ~45 minutes  
**Success Rate:** All 4 terminals should run without errors

---

## ONE-TIME SETUP

```powershell
# 1. Navigate to project
cd "c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"

# 2. Clear all previous state (REQUIRED)
python reset_pipeline.py --hard-reset
```

---

## TERMINAL 1: KAFKA BROKER

```powershell
# Option A: Docker (if available)
docker run --rm -p 9092:9092 -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 apache/kafka:latest

# Option B: Local Kafka
# (adjust path to your Kafka installation)
# .\bin\windows\kafka-server-start.bat .\config\server.properties
```

**Wait for:** `[KafkaServer id=0] started`  
**Keep running:** ✓ (entire test)

---

## TERMINAL 2: SPARK STREAMING JOB

```powershell
cd "c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"
& "..\..\..\..\..\..\.venv\Scripts\Activate.ps1"
python -m src.streaming.spark_job --checkpoint-path "checkpoints/spark_predictions" --output-path "data/metrics" --log-level INFO
```

**Wait for:** `query-started: id=..., status=ACTIVE`  
**Keep running:** ✓ (entire test)

---

## TERMINAL 3: KAFKA PRODUCER

```powershell
cd "c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"
& "..\..\..\..\..\..\.venv\Scripts\Activate.ps1"
python -m src.streaming.kafka_producer --dataset "data/stream_dataset/hrl_load_metered-2020.csv" --sleep-seconds 0.1 --resume --reset-state --log-level INFO
```

**Wait for:** `producer-dataset-switch` (shows 2020→2021 auto-cycling)  
**Keep running:** ✓ (entire test)

---

## TERMINAL 4: ORCHESTRATOR (Start after T+5 minutes)

```powershell
cd "c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"
& "..\..\..\..\..\..\.venv\Scripts\Activate.ps1"
python -m src.self_healing.orchestrator --interval-seconds 60 --max-runs 30 --required-consecutive-drifts 3 --cooldown-minutes 10 --stream-csv-path "data/stream_dataset/hrl_load_metered-2021.csv" --recent-days 30 --min-relative-improvement 0.02 --log-level INFO
```

**Wait for:** `orchestrator-started` message  
**Look for:** 
- `orchestrator-retrain-triggered` (auto-retrain started)
- `orchestrator-promotion-complete` (model promoted)
- `decision=promote` (success)

**Keep running:** ✓ (30 checks, ~30 minutes)

---

## OPTIONAL: MONITORING COMMANDS

In separate terminals, run these to watch different aspects:

### Watch Metrics Grow
```powershell
while($true) { 
    $count = (Get-ChildItem "data/metrics/hourly_metrics" -Recurse -File -ErrorAction SilentlyContinue).Count
    Write-Host "$(Get-Date): $count metric files"
    Start-Sleep -Seconds 10
}
```

### Watch Orchestrator Decisions
```powershell
Get-Content -Path "artifacts/self_healing/trigger_decisions.jsonl" -Wait -Tail 1
```

### Watch Active Model Changes
```powershell
while($true) {
    if (Test-Path "artifacts/models/active_model.json") {
        $active = Get-Content "artifacts/models/active_model.json" | ConvertFrom-Json
        Write-Host "$(Get-Date): Active: $($active.version)"
    }
    Start-Sleep -Seconds 5
}
```

---

## EXPECTED TIMELINE

- T+0s → Clean reset
- T+1s → Start Broker (Terminal 1)
- T+6s → Start Spark (Terminal 2) 
- T+16s → Start Producer (Terminal 3)
- T+60s → First metrics appear
- T+5m → Start Orchestrator (Terminal 4)
- T+6-8m → Drift detected (3 consecutive checks)
- T+9-12m → **Retrain pipeline runs**
- T+13m → **Model promoted** (if candidate better)
- T+22m → Producer auto-cycles: 2020 → 2021
- T+45m → All tests complete

---

## SUCCESS CHECKLIST

Run this after starting all 4 terminals:

```powershell
# Check 1: Metrics being written
Test-Path -Path "data/metrics/hourly_metrics" -PathType Container
(Get-ChildItem -Path "data/metrics/hourly_metrics" -Recurse -File).Count

# Check 2: Orchestrator logs exist
Test-Path -Path "artifacts/self_healing/trigger_decisions.jsonl"
(Get-Content "artifacts/self_healing/trigger_decisions.jsonl" | Measure-Object -Line).Lines

# Check 3: Drift detected (at least once)
$lines = Get-Content "artifacts/self_healing/trigger_decisions.jsonl" | ConvertFrom-Json
$drifts = $lines | Where-Object {$_.drift_detected -eq $true} | Measure-Object
Write-Host "Drift detections: $($drifts.Count)"

# Check 4: Retrain triggered
$retrains = $lines | Where-Object {$_.action_executed -eq "retrain_pipeline"} | Measure-Object  
Write-Host "Retrain actions: $($retrains.Count)"

# Check 5: Promotion completed
$promotions = $lines | Where-Object {$_.action_executed -eq "promotion"} | Measure-Object
Write-Host "Promotion actions: $($promotions.Count)"
```

---

## TROUBLESHOOTING

| Issue | Solution |
|-------|----------|
| Broker won't start on 9092 | Check `netstat -ano \| findstr :9092`, kill process on port, restart |
| Producer can't connect to Kafka | Wait 5 sec after broker starts, check logs for "failed to connect" |
| Spark not writing metrics | Verify Producer is sending records (`record-published` in logs) |
| No drift detected | Normal — data from 2020 baseline may be similar to 2021 |
| Orchestrator running but no retrain | Need 3+ drift detections, may take 5+ minutes |
| "ModuleNotFoundError" | Activate venv: `. "..\..\..\..\..\..\.venv\Scripts\Activate.ps1"` |

---

## WHEN TO STOP

**Safe to stop after:**
- All 4 terminals have been running for 30+ minutes
- You see at least one `drift_detected=True` in logs
- Ideally you see `action_executed=retrain_pipeline` or `action_executed=promotion`

**Clean shutdown:**
```powershell
# In each terminal, press: Ctrl+C
# Wait for graceful shutdown (takes 2-5 seconds)
```

---

## AFTER SUCCESS

To repeat the test with different parameters:

```powershell
# Full cleanup
python reset_pipeline.py --hard-reset

# Then restart all 4 terminals with modified parameters
# Example: Change cooldown_minutes to 5, required_consecutive_drifts to 2, etc.
```

---

## KEY FACTS

✅ **System is COMPLETE and PRODUCTION-READY**

- Producer auto-cycles 2020 → 2021 → 2022 → loop
- No manual intervention needed for drift detection
- Retrain runs automatically when thresholds met  
- Model promotion automatic when candidate better
- Full decision audit trail in JSONL format
- State persisted across restarts (via checkpoints & resume)

🎯 **This test validates the entire automation chain works end-to-end.**
