#!/usr/bin/env python
"""
End-to-End Test Validation Helper

Run this while tests are in progress to check system health and progress.
Usage: python validate_test.py
"""

from pathlib import Path
import json
from datetime import datetime
import sys

def _project_root() -> Path:
    return Path(__file__).resolve().parent

def check_prerequisites():
    """Verify required datasets exist."""
    print("\n=== CHECKING PREREQUISITES ===")
    datasets = [
        "data/stream_dataset/hrl_load_metered-2020.csv",
        "data/stream_dataset/hrl_load_metered-2021.csv",
    ]
    
    root = _project_root()
    all_exist = True
    for ds in datasets:
        path = root / ds
        exists = path.exists()
        status = "✓" if exists else "✗"
        print(f"  {status} {ds}")
        all_exist = all_exist and exists
    
    return all_exist


def check_checkpoint_cleanup():
    """Verify pipeline state was reset."""
    print("\n=== CHECKING CLEANUP STATE ===")
    
    root = _project_root()
    
    # These should be empty after reset
    check_dirs = {
        "data/metrics/hourly_metrics": "Hourly metrics",
        "data/predictions": "Predictions",
        "checkpoints/spark_predictions": "Spark checkpoints",
        "artifacts/drift": "Drift reports",
        "artifacts/self_healing": "Orchestrator decisions",
    }
    
    all_clean = True
    for rel_path, name in check_dirs.items():
        path = root / rel_path
        if path.exists():
            items = list(path.rglob("*"))
            is_empty = len(items) == 0
            status = "✓ empty" if is_empty else f"✗ {len(items)} item(s)"
            print(f"  {status} {name}")
            all_clean = all_clean and is_empty
        else:
            print(f"  ✓ not created (will be on startup) {name}")
    
    return all_clean


def check_metrics_accumulation():
    """Check how many hourly metrics have been written."""
    # Measures pipeline throughput indirectly via parquet shard count.
    print("\n=== CHECKING METRICS ACCUMULATION ===")
    
    root = _project_root()
    metrics_dir = root / "data" / "metrics" / "hourly_metrics"
    
    if not metrics_dir.exists():
        print("  ✗ No metrics directory (Spark job not running or no data)")
        return 0
    
    metric_files = list(metrics_dir.rglob("*.parquet"))
    total_metrics = len(metric_files)
    print(f"  Metric files: {total_metrics}")
    
    if total_metrics < 100:
        print("    → Still accumulating (early stage)")
    elif total_metrics < 500:
        print("    → Good progress (5-10 minutes)")
    elif total_metrics < 1000:
        print("    → Substantial data (15+ minutes)")
    else:
        print("    → Large dataset (30+ minutes)")
    
    return total_metrics


def check_drift_detection():
    """Check if drift has been detected."""
    print("\n=== CHECKING DRIFT DETECTION ===")
    
    root = _project_root()
    history_path = root / "artifacts" / "drift" / "drift_history.jsonl"
    
    if not history_path.exists():
        print("  ✗ No drift history (orchestrator not running)")
        return {"checks": 0, "drifts": 0}
    
    lines = history_path.read_text().strip().split("\n")
    total_checks = len([l for l in lines if l.strip()])
    
    drift_count = 0
    for line in lines:
        if line.strip():
            try:
                obj = json.loads(line)
                if obj.get("drift_detected"):
                    drift_count += 1
            except:
                pass
    
    print(f"  Total checks: {total_checks}")
    print(f"  Drift detections: {drift_count}")
    
    if drift_count >= 3:
        print("    → Threshold met (retrain should be triggered)")
    elif drift_count > 0:
        print(f"    → Drift detected ({3 - drift_count} more needed for action)")
    else:
        print("    → No drift yet (may be normal)")
    
    return {"checks": total_checks, "drifts": drift_count}


def check_orchestrator_decisions():
    """Check orchestrator action log."""
    # Summarizes decisions to show policy progression over time.
    print("\n=== CHECKING ORCHESTRATOR DECISIONS ===")
    
    root = _project_root()
    decision_log = root / "artifacts" / "self_healing" / "trigger_decisions.jsonl"
    
    if not decision_log.exists():
        print("  ✗ No decision log (orchestrator not running)")
        return None
    
    lines = decision_log.read_text().strip().split("\n")
    total_decisions = len([l for l in lines if l.strip()])
    
    actions = {}
    for line in lines:
        if line.strip():
            try:
                obj = json.loads(line)
                action = obj.get("trigger_decision", "unknown")
                actions[action] = actions.get(action, 0) + 1
            except:
                pass
    
    print(f"  Total decisions logged: {total_decisions}")
    for action, count in sorted(actions.items()):
        print(f"    - {action}: {count}")
    
    retrain_count = actions.get("retrain_candidate", 0)
    promote_count = actions.get("promote_candidate", 0)
    
    if promote_count > 0:
        print("  ✓ PROMOTION TRIGGERED (success!)")
    elif retrain_count > 0:
        print("  ✓ Retrain triggered (waiting for promotion eligibility check)")
    elif total_decisions > 5:
        print("  → Still evaluating (no action yet, normal)")
    else:
        print("  → Starting (not enough data for decision)")
    
    return actions


def check_candidate_model():
    """Check if candidate model was created."""
    print("\n=== CHECKING CANDIDATE MODEL ===")
    
    root = _project_root()
    candidates_dir = root / "artifacts" / "models" / "candidates"
    
    if not candidates_dir.exists():
        print("  ✗ No candidates directory (retrain not run)")
        return False
    
    candidate_files = list(candidates_dir.glob("*.joblib"))
    if candidate_files:
        latest = sorted(candidate_files)[-1]
        print(f"  ✓ Candidate model: {latest.name}")
        return True
    else:
        print("  ✗ No candidate models yet")
        return False


def check_active_model_updated():
    """Check if active model pointer was updated."""
    print("\n=== CHECKING ACTIVE MODEL ===")
    
    root = _project_root()
    active_path = root / "artifacts" / "models" / "active_model.json"
    
    if not active_path.exists():
        print("  ✗ No active model file")
        return False
    
    try:
        active = json.loads(active_path.read_text())
        version = active.get("version", "unknown")
        print(f"  Current active model: {version}")
        
        if "candidate" in version:
            print("  ✓ MODEL PROMOTED (candidate is now active)")
            return True
        elif "model_v" in version:
            print("  → Base model active (no promotion yet)")
            return False
    except Exception as e:
        print(f"  ✗ Error reading active model: {e}")
        return False


def check_producer_state():
    """Check producer status."""
    print("\n=== CHECKING PRODUCER STATE ===")
    
    root = _project_root()
    state_path = root / "checkpoints" / "producer" / "producer_state.json"
    
    if not state_path.exists():
        print("  ✗ No producer state (not started)")
        return None
    
    try:
        state = json.loads(state_path.read_text())
        dataset_index = state.get("dataset_index", 0)
        dataset_sequence = state.get("dataset_sequence", [])
        current_dataset = dataset_sequence[dataset_index] if dataset_index < len(dataset_sequence) else "?"
        
        if "2021" in current_dataset:
            print("  ✓ Producer cycling: 2020 → 2021 (auto-cycle working)")
        elif "2020" in current_dataset:
            print("  → Producer on 2020 (waiting for auto-cycle to 2021)")
        
        rows = state.get("rows", 0)
        next_index = state.get("next_index", 0)
        progress = (next_index / rows * 100) if rows > 0 else 0
        print(f"    Progress: {next_index}/{rows} ({progress:.1f}%)")
        
        return state
    except Exception as e:
        print(f"  ✗ Error reading producer state: {e}")
        return None


def main():
    """Run validation checks."""
    # ----------------------------------------------------
    # ---------------- Validation Summary ----------------
    # Aggregates all checks and prints current E2E stage.
    # ----------------------------------------------------
    print("=" * 60)
    print("END-TO-END TEST VALIDATION")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Sequential checks
    prereqs_ok = check_prerequisites()
    cleanup_ok = check_checkpoint_cleanup()
    metrics_count = check_metrics_accumulation()
    drift_info = check_drift_detection()
    decisions = check_orchestrator_decisions()
    candidate_ok = check_candidate_model()
    active_updated = check_active_model_updated()
    producer_state = check_producer_state()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if metrics_count == 0:
        print("🔴 Stage: Startup (no metrics yet)")
        print("   Next: Start Spark job if not running")
    elif metrics_count < 100:
        print("🟡 Stage: Early accumulation (5-10 min in)")
        print("   Next: Producer sending data, Spark is writing metrics")
    elif metrics_count < 500:
        print("🟡 Stage: Mid-test (10-20 min in)")
        print("   Next: Wait for orchestrator to detect drift")
    elif drift_info["drifts"] == 0:
        print("🟡 Stage: Metrics ready, waiting for drift check")
        print("   Next: Orchestrator should start detecting drift")
    elif drift_info["drifts"] < 3:
        print("🟡 Stage: Drift detected, building threshold")
        print(f"   Next: {3 - drift_info['drifts']} more drift checks for retrain trigger")
    elif not candidate_ok:
        print("🟡 Stage: Retrain triggered, model training in progress")
        print("   Next: Wait for candidate model to be created")
    elif not active_updated:
        print("🟡 Stage: Candidate created, evaluating for promotion")
        print("   Next: If candidate is better, will be promoted to active")
    else:
        print("🟢 STAGE: SUCCESS - Full automation cycle complete!")
        print("   ✓ Model promoted (active model updated)")
        print("   ✓ Drift detection working")
        print("   ✓ Retrain pipeline working")
        print("   ✓ Auto-promotion working")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    
    if not prereqs_ok:
        print("1. Verify datasets exist in data/stream_dataset/")
    if metrics_count < 100:
        print("1. Check Producer is sending records (Terminal 3 logs)")
        print("2. Check Spark job is running (Terminal 2 logs, http://localhost:4040)")
    if drift_info["drifts"] == 0 and metrics_count > 100:
        print("1. Start Orchestrator if not running (Terminal 4)")
        print("2. Wait a few more minutes for first drift check")
    if decisions and "retrain_candidate" not in decisions and metrics_count > 200:
        print("1. Check orchestrator logs for drift detection")
        print("2. Data from same year may not show drift (normal)")
    if candidate_ok and not active_updated:
        print("1. Check candidate report: artifacts/models/candidate_report.json")
        print("2. If candidate is not better, promotion won't happen (expected)")
    
    print("\nRun this script again in 2-3 minutes to see progress.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error during validation: {e}")
        sys.exit(1)
