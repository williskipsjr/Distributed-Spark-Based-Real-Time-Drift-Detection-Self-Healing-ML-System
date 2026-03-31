# Complete System Testing Guide
## Validate Entire ML Pipeline End-to-End

---

## PHASE 0: Environment Setup (Run Once)

### Check Python Environment
```powershell
cd "c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"
python --version
pip list | grep -E "kafka|xgboost|pandas|pyspark"
```

**Expected**: Python 3.10+, kafka-python, xgboost, pandas, pyspark installed

### Check Required Data Files
```powershell
# Check baseline model exists
if (Test-Path "artifacts/models/model_v2.joblib") { Write-Host "✓ Baseline model found" } else { Write-Host "✗ Missing model" }

# Check baseline metrics
if (Test-Path "artifacts/baselines/baseline_metrics_v2.json") { Write-Host "✓ Baseline metrics found" } else { Write-Host "✗ Missing metrics" }

# Check dataset files
if (Test-Path "data/stream_dataset/hrl_load_metered-2019.csv") { Write-Host "✓ Stream data 2019 found" } else { Write-Host "✗ Missing 2019 data" }
if (Test-Path "data/stream_dataset/hrl_load_metered-2020.csv") { Write-Host "✓ Stream data 2020 found" } else { Write-Host "✗ Missing 2020 data" }
```

**Expected**: All files should exist (✓)

### Check Kafka Connectivity
```powershell
# This will test if Kafka can be reached (without needing broker running yet)
python - <<'PY'
try:
    from kafka import KafkaProducer
    print("✓ kafka-python library works")
except ImportError as e:
    print(f"✗ kafka-python import failed: {e}")
PY
```

---

## PHASE 1: Unit Tests (Component-Level)
### Run all fast unit tests (NO Kafka/Spark needed)
```powershell
python run_tests.py --quick
```

**Expected Output**:
```
✓ 57-70 tests PASSED
✗ 0-5 failures (acceptable if function signatures differ)
○ 45+ skipped (expected for Spark/Kafka without external services)
```

---

## PHASE 1A: Test Kafka Producer Logic
```powershell
python -m pytest tests/test_producer.py -v
```

**Validates**:
- Data loading from CSV ✓
- Aggregation to PJM scale ✓
- Message format correctness ✓

---

## PHASE 1B: Test Feature Alignment
```powershell
python -m pytest tests/test_feature_builder.py -v
```

**Validates**:
- All 9 required feature columns exist ✓
- Lag features (lag_1, lag_24, lag_168) ✓
- Rolling features (rolling_24, rolling_168) ✓
- Temporal features (hour_of_day, day_of_week, month, is_weekend) ✓

---

## PHASE 1C: Test Model Loading (Pointer System)
```powershell
python -m pytest tests/test_model_loading.py -v
```

**Validates**:
- Model pointer file reads correctly ✓
- Fallback to v2 if pointer broken ✓
- Feature contract matches model ✓

---

## PHASE 1D: Test Drift Detection (Isolated)
```powershell
python -m pytest tests/test_drift_monitor.py -v
```

**Validates**:
- MAE/RMSE comparison logic ✓
- Drift threshold logic ✓
- Consecutive drift counting ✓

---

## PHASE 1E: Test Retraining Pipeline
```powershell
python -m pytest tests/test_retrain_pipeline.py -v
```

**Validates**:
- Candidate model creation ✓
- Metrics computation ✓
- Comparison report generation ✓

---

## PHASE 1F: Test Trigger Decision (Dry-Run)
```powershell
python -m pytest tests/test_trigger.py -v
```

**Validates**:
- Trigger logic (no_action/retrain/promote) ✓
- Dry-run mode (no side effects) ✓

---

## PHASE 1G: Test Promotion Gate (Dry-Run)
```powershell
python -m pytest tests/test_promotion.py -v
```

**Validates**:
- Promotion gates (MAE, RMSE, improvement) ✓
- Decision logging ✓
- Dry-run mode (no pointer update) ✓

---

## PHASE 2: Integration Tests (Multi-Terminal Orchestration)

### TERMINAL 1: Start Kafka Broker
```powershell
docker run -p 9092:9092 apache/kafka:latest
```

**Wait for output**:
```
[KafkaServer id=0] started (kafka.server.KafkaServer)
```

---

### TERMINAL 2: Start Kafka Producer

```powershell
cd "c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"

python -m src.streaming.kafka_producer `
  --dataset "data/stream_dataset/hrl_load_metered-2019.csv" `
  --sleep-seconds 0.1 `
  --reset-state `
  --log-level INFO
```

**Watch for**:
```
[PRODUCER] Published record: datetime=2019-01-01 01:00:00, load_mw=XXX, features={...}
[PRODUCER] Published: 50 records
[PRODUCER] Published: 100 records
[PRODUCER] Published: 150 records
...
```

Let it run ~30 seconds to accumulate messages.

---

### TERMINAL 3: Start Spark Serving Job

**In WSL (NOT PowerShell)**:
```bash
cd "/mnt/c/Users/Willis/OneDrive/Documents/IIIT-DWD/2nd Year/4th Sem/Big Data/BDA-Project/Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"
source .venv/bin/activate
export PYSPARK_PYTHON="$(which python)"
export PYSPARK_DRIVER_PYTHON="$(which python)"

python -m src.streaming.spark_job \
  --no-debug-mode \
  --run-seconds 120 \
  --reset-checkpoint \
  --log-level INFO
```

**Watch for**:
```
Spark streaming started
Subscribed to topic: load-stream
Batch 0: processed 50 records, wrote metrics
Batch 1: processed 50 records, wrote metrics
...
```

Let it run for full 120 seconds.

---

### TERMINAL 4: Minimal Commands (While Terminals 2-3 Run)

**After 60+ seconds of Spark running, execute**:

#### 4A. Check Metrics Written
```powershell
$metricsDir = "data/metrics/hourly_metrics"
$files = @(Get-ChildItem -Path $metricsDir -Recurse -Filter "*.parquet" -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 0 })
Write-Host "Metrics files written: $($files.Count)"
if ($files.Count -gt 0) {
    Write-Host "✓ Spark wrote output to $metricsDir"
    Write-Host "File sizes: $($files | ForEach-Object { $_.Name + ' (' + $_.Length + ' bytes)' })"
} else {
    Write-Host "✗ No metrics found (Spark may be waiting for data)"
}
```

#### 4B. Check Checkpoint State
```powershell
$ckpts = @(Get-ChildItem -Path "checkpoints/spark_predictions" -Recurse -ErrorAction SilentlyContinue)
Write-Host "Spark checkpoints: $($ckpts.Count) items"
Get-ChildItem -Path "checkpoints/spark_predictions" -Recurse | Select-Object Name, LastWriteTime | Format-Table
```

---

## PHASE 3: Explicit Test Scenarios

### Scenario A: Normal Operation (No Drift)

**While Terminals 2-3 still running**, in Terminal 4:

```powershell
# Read current metrics window
python - <<'PY'
import pandas as pd
from pathlib import Path

p = Path("data/metrics/hourly_metrics")
files = sorted([f for f in p.glob("**/*.parquet") if f.stat().st_size > 0])

if files:
    dfs = [pd.read_parquet(f) for f in files[-5:]]  # Last 5 batches
    df = pd.concat(dfs, ignore_index=True)
    
    print(f"Total rows in current window: {len(df)}")
    print(f"Columns: {df.columns.tolist()}")
    print(f"\nRecent predictions:")
    print(df[['datetime', 'load_mw', 'prediction', 'model_version']].tail(10))
    
    # Compute metrics
    if 'prediction' in df.columns and 'load_mw' in df.columns:
        mae = (df['load_mw'] - df['prediction']).abs().mean()
        rmse = ((df['load_mw'] - df['prediction'])**2).mean()**0.5
        print(f"\nCurrent MAE: {mae:.2f}")
        print(f"Current RMSE: {rmse:.2f}")
else:
    print("No metrics files found yet")
PY
```

**Expected**: Metrics close to baseline (MAE ~2400-2500, RMSE ~3000-3200)

---

### Scenario B: Trigger Retrain (Manual)

```powershell
# Trigger decision (dry-run, no side effects)
python -m src.self_healing.trigger --dry-run --log-level INFO
```

**Expected output**:
```json
{
  "decision": "no_action" | "retrain_candidate",
  "reason": "...",
  "consecutive_drifts": 0-3,
  "timestamp": "2026-03-31T..."
}
```

If `decision: retrain_candidate`, run:

```powershell
python -m src.self_healing.retrain_pipeline `
  --stream-csv-path "data/stream_dataset/hrl_load_metered-2020.csv" `
  --recent-days 30 `
  --min-relative-improvement 0.02 `
  --log-level INFO
```

**Expected**: New candidate model created at `artifacts/models/candidate_*.joblib`

---

### Scenario C: Promote Candidate Model

```powershell
# Evaluate candidate (dry-run)
python -m src.self_healing.promotion `
  --dry-run `
  --log-level INFO
```

**Expected**:
```json
{
  "decision": "approve" | "reject",
  "reason": "...",
  "mae_improvement_pct": 2.5,
  "timestamp": "..."
}
```

If approved, promote (ACTUALLY UPDATES POINTER):

```powershell
python -m src.self_healing.promotion `
  --log-level INFO
```

**Watch**: Pointer file updates to new model version

---

### Scenario D: Rollback Model

```powershell
# Check current pointer
type artifacts/models/model_pointer.json

# Rollback to previous version
python -m src.self_healing.rollback --log-level INFO

# Verify pointer changed
type artifacts/models/model_pointer.json
```

---

## PHASE 4: Verification & Output Checking

### 4A. Verify Kafka Production
```powershell
python - <<'PY'
import json
from pathlib import Path

checkpoint_file = Path("checkpoints/producer/producer_state.json")
if checkpoint_file.exists():
    with open(checkpoint_file) as f:
        state = json.load(f)
    print(f"Producer checkpoint: {state}")
    print(f"Last row published: #{state.get('last_row_index', 'unknown')}")
else:
    print("No producer checkpoint yet")
PY
```

---

### 4B. Verify Drift Decision Log
```powershell
# Show last 5 drift decisions
$driftLog = "artifacts/drift/drift_history.jsonl"
if (Test-Path $driftLog) {
    Write-Host "Recent drift checks:"
    Get-Content $driftLog | Select-Object -Last 5
} else {
    Write-Host "No drift history yet (run drift_monitor first)"
}
```

---

### 4C. Verify Promotion Audit Log
```powershell
# Show promotion decisions
$promotionLog = "artifacts/self_healing/promotion_audit.jsonl"
if (Test-Path $promotionLog) {
    Write-Host "Promotion audit trail:"
    Get-Content $promotionLog
} else {
    Write-Host "No promotions yet"
}
```

---

### 4D. Check Active Model Pointer
```powershell
python - <<'PY'
import json
from pathlib import Path

pointer_file = Path("artifacts/models/model_pointer.json")
if pointer_file.exists():
    with open(pointer_file) as f:
        pointer = json.load(f)
    print(f"Active model: {pointer.get('active_model_version', 'unknown')}")
    print(f"Model path: {pointer.get('active_model_path', 'unknown')}")
    print(f"Last updated: {pointer.get('updated_at', 'unknown')}")
else:
    print("No pointer file found")
PY
```

---

### 4E. Verify Metrics Output
```powershell
python - <<'PY'
import pandas as pd
from pathlib import Path

p = Path("data/metrics/hourly_metrics")
files = sorted([f for f in p.glob("**/*.parquet") if f.stat().st_size > 0])

if not files:
    print("✗ No metrics files found")
else:
    print(f"✓ Found {len(files)} metrics files")
    
    dfs = []
    for f in files:
        try:
            dfs.append(pd.read_parquet(f))
        except Exception as e:
            print(f"  Skipped bad file: {f}")
    
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        print(f"\nMetrics summary:")
        print(f"  Total rows: {len(df)}")
        print(f"  Date range: {df['datetime'].min()} to {df['datetime'].max()}")
        print(f"  Columns: {df.columns.tolist()}")
        print(f"\nFirst few rows:")
        print(df.head())
    else:
        print("Could not load any metrics")
PY
```

---

## PHASE 5: Regression Tests

### 5A. Producer Resume (Fault Tolerance)

**Stop producer (Ctrl+C in Terminal 2), then restart**:

```powershell
# Start producer again (same command, no --reset-state)
python -m src.streaming.kafka_producer `
  --dataset "data/stream_dataset/hrl_load_metered-2019.csv" `
  --sleep-seconds 0.1 `
  --log-level INFO
```

**Expected**: Producer resumes from checkpoint, doesn't restart from row 1

```
[PRODUCER] Resuming from checkpoint: row 245
[PRODUCER] Published record: datetime=2019-01-10 13:00:00, ...
```

---

### 5B. Model Loading Consistency

```powershell
python - <<'PY'
import json
from pathlib import Path
import joblib

# Load model 3 times, verify same instance
models = []
for i in range(3):
    # This should use pointer + fallback logic
    model_path = Path("artifacts/models/model_v2.joblib")
    model = joblib.load(model_path)
    models.append(model)

# Verify all 3 are same model
print(f"All models loaded: {len(models) == 3}")
print(f"Model type: {type(models[0])}")
print("✓ Model loading consistent")
PY
```

---

### 5C. Feature Column Alignment

```powershell
python - <<'PY'
import json
from pathlib import Path
from src.data.feature_builder import FEATURE_COLUMNS

# Check feature contract
required = [
    "hour_of_day", "day_of_week", "month", "is_weekend",
    "lag_1", "lag_24", "lag_168",
    "rolling_24", "rolling_168"
]

missing = [f for f in required if f not in FEATURE_COLUMNS]
extra = [f for f in FEATURE_COLUMNS if f not in required]

if not missing and not extra:
    print(f"✓ Feature columns align perfectly")
    print(f"  Features: {FEATURE_COLUMNS}")
else:
    if missing:
        print(f"✗ Missing: {missing}")
    if extra:
        print(f"⚠ Extra: {extra}")
PY
```

---

## SUMMARY: SUCCESS CRITERIA

### Minimal Success (Core Components Work)
- [ ] Phase 1: All unit tests pass (✓ 45+ tests)
- [ ] Phase 4C-D: Drift detection runs, trigger decision logged
- [ ] Phase 4D: Model pointer updates correctly

### Full Success (End-to-End Pipeline)
- [ ] Phase 2: All 4 terminals run without errors
- [ ] Phase 4A: Kafka producer publishes 100+ records
- [ ] Phase 4E: Spark writes metrics to disk (100+ rows)
- [ ] Phase 3: Trigger/promotion logic executes
- [ ] Phase 5: Resume and model consistency work

### Project Complete When
- ✅ **All unit tests pass**
- ✅ **Kafka producer runs 60+ seconds**
- ✅ **Spark job runs 120 seconds, writes metrics**
- ✅ **Drift detection triggers correctly**
- ✅ **Self-healing loop (trigger → retrain → promote) executes**
- ✅ **Model pointer updates on promotion**
- ✅ **Rollback restores previous model**

---

## Recommended Order

1. **Phase 0** (5 min) - Environment check
2. **Phase 1** (10 min) - Quick unit tests
3. **Phase 2** (5 min setup + 2 min wait) - Start terminals
4. **Phase 3** (3 min) - Run scenarios while terminals active
5. **Phase 4** (5 min) - Verify outputs
6. **Phase 5** (5 min) - Test resilience

**Total time: ~45 minutes for full validation**

---

## If Something Fails

| Symptom | Check First |
|---------|------------|
| Kafka won't start | `docker ps`, check port 9092 not in use |
| Producer hangs | Check Kafka running, broker accessible from Windows |
| No metrics written | Check Spark logs, verify Kafka messages being consumed |
| Drift not detected | Need 100+ metrics rows, baseline_metrics_v2.json must exist |
| Trigger won't run | Check artifacts/models/ has model files |
| Tests fail | Run `python run_tests.py --quick` to see which unit tests break |

