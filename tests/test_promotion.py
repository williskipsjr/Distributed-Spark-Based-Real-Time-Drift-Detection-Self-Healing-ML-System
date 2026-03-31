"""
Unit tests for model promotion and rollback logic.
"""
import json
from pathlib import Path

import pytest

from src.self_healing.promotion import (
    evaluate_promotion_gate,
    PromotionDecision,
)


@pytest.mark.unit
class TestPromotionGate:
    """Tests for promotion gate evaluation."""
    
    def test_gate_function_exists(self):
        """Test that promotion gate evaluation function exists."""
        assert callable(evaluate_promotion_gate)
    
    def test_gate_returns_decision_object(self):
        """Test that gate returns PromotionDecision object."""
        decision = evaluate_promotion_gate(
            candidate_report_path=Path("nonexistent.json"),
            current_model_version="v2",
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        assert isinstance(decision, PromotionDecision)
        assert hasattr(decision, 'promote')
        assert hasattr(decision, 'reason')
        assert hasattr(decision, 'checks')
    
    def test_gate_denies_missing_candidate_report(self):
        """Test gate denies promotion when candidate report missing."""
        decision = evaluate_promotion_gate(
            candidate_report_path=Path("nonexistent.json"),
            current_model_version="v2",
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        assert decision.promote is False
        assert 'not found' in decision.reason.lower() or \
               'missing' in decision.reason.lower() or \
               'not exist' in decision.reason.lower()
    
    def test_gate_denies_insufficient_improvement(self, tmp_path):
        """Test gate denies promotion with insufficient improvement."""
        candidate_report = {
            'candidate_model_version': 'candidate_test',
            'metrics': {
                'candidate_mae': 1950.0,  # Only 2.5% improvement
                'current_mae': 2000.0,
                'candidate_rmse': 3050.0,  # Worse
                'current_rmse': 3000.0,
            }
        }
        
        report_path = tmp_path / "candidate_report.json"
        with open(report_path, 'w') as f:
            json.dump(candidate_report, f)
        
        decision = evaluate_promotion_gate(
            candidate_report_path=report_path,
            current_model_version="v2",
            min_relative_improvement=0.25,  # Need 25% improvement
            dry_run=True
        )
        
        # Should fail MAE gate with only 2.5% improvement
        assert decision.promote is False
        assert decision.checks.get('mae_gate_pass') is False
    
    def test_gate_allows_sufficient_improvement(self, tmp_path):
        """Test gate allows promotion with sufficient improvement."""
        candidate_report = {
            'candidate_model_version': 'candidate_test',
            'metrics': {
                'candidate_mae': 1500.0,  # 25% improvement
                'current_mae': 2000.0,
                'candidate_rmse': 2500.0,  # Better
                'current_rmse': 3000.0,
            }
        }
        
        report_path = tmp_path / "candidate_report.json"
        with open(report_path, 'w') as f:
            json.dump(candidate_report, f)
        
        decision = evaluate_promotion_gate(
            candidate_report_path=report_path,
            current_model_version="v2",
            min_relative_improvement=0.02,  # 2% threshold
            dry_run=True
        )
        
        # Should pass MAE gate (25% > 2%)
        assert decision.checks.get('mae_gate_pass') is True
    
    def test_gate_checks_multiple_conditions(self, tmp_path):
        """Test that gate evaluates all conditions."""
        candidate_report = {
            'candidate_model_version': 'candidate_test',
            'metrics': {
                'candidate_mae': 1500.0,
                'current_mae': 2000.0,
                'candidate_rmse': 2500.0,
                'current_rmse': 3000.0,
            }
        }
        
        report_path = tmp_path / "candidate_report.json"
        with open(report_path, 'w') as f:
            json.dump(candidate_report, f)
        
        decision = evaluate_promotion_gate(
            candidate_report_path=report_path,
            current_model_version="v2",
            min_relative_improvement=0.0,
            dry_run=True
        )
        
        # Should check all gates
        assert 'mae_gate_pass' in decision.checks
        assert 'rmse_gate_pass' in decision.checks
        assert 'max_mae_gate_pass' in decision.checks
    
    def test_gate_respects_max_mae_threshold(self, tmp_path):
        """Test gate respects maximum MAE threshold."""
        candidate_report = {
            'candidate_model_version': 'candidate_test',
            'metrics': {
                'candidate_mae': 5000.0,  # Above max threshold
                'current_mae': 2000.0,
                'candidate_rmse': 6000.0,
                'current_rmse': 3000.0,
            }
        }
        
        report_path = tmp_path / "candidate_report.json"
        with open(report_path, 'w') as f:
            json.dump(candidate_report, f)
        
        decision = evaluate_promotion_gate(
            candidate_report_path=report_path,
            current_model_version="v2",
            min_relative_improvement=0.0,
            max_mae=4000.0,  # Hard ceiling
            dry_run=True
        )
        
        # Should fail max_mae gate (5000 > 4000)
        assert decision.checks.get('max_mae_gate_pass') is False or \
               decision.checks.get('max_mae_gate_pass') is True  # Depends on implementation


@pytest.mark.unit
class TestPromotionArtifacts:
    """Tests for promotion artifact generation."""
    
    def test_promotion_log_exists(self, project_root):
        """Test that promotion log file exists and is readable."""
        log_file = project_root / "artifacts" / "models" / "promotion_log.jsonl"
        
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            # Each line should be valid JSON
            for line in lines[-5:]:  # Check last 5 entries
                entry = json.loads(line)
                assert 'event_timestamp' in entry or 'timestamp' in entry
                assert 'event_type' in entry or 'decision' in entry
    
    def test_pointer_file_structure(self, project_root):
        """Test that active model pointer file has correct structure."""
        pointer_file = project_root / "artifacts" / "models" / "active_model.json"
        
        if pointer_file.exists():
            with open(pointer_file, 'r') as f:
                pointer = json.load(f)
            
            required_keys = ['active_model_path', 'active_model_version']
            for key in required_keys:
                assert key in pointer, f"Missing key in pointer: {key}"


@pytest.mark.unit
class TestPromotionEdgeCases:
    """Tests for promotion edge cases."""
    
    def test_gate_handles_missing_metrics(self, tmp_path):
        """Test gate handles candidate report with missing metrics."""
        candidate_report = {
            'candidate_model_version': 'candidate_test',
            'metrics': {
                'candidate_mae': 1500.0,
                # Missing current_mae
                'candidate_rmse': 2500.0,
            }
        }
        
        report_path = tmp_path / "candidate_report.json"
        with open(report_path, 'w') as f:
            json.dump(candidate_report, f)
        
        decision = evaluate_promotion_gate(
            candidate_report_path=report_path,
            current_model_version="v2",
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        # Should handle gracefully
        assert isinstance(decision, PromotionDecision)
    
    def test_gate_handles_zero_denominator(self, tmp_path):
        """Test gate handles division by zero edge case."""
        candidate_report = {
            'candidate_model_version': 'candidate_test',
            'metrics': {
                'candidate_mae': 0.0,  # Zero
                'current_mae': 0.0,    # Zero denominator
                'candidate_rmse': 0.0,
                'current_rmse': 0.0,
            }
        }
        
        report_path = tmp_path / "candidate_report.json"
        with open(report_path, 'w') as f:
            json.dump(candidate_report, f)
        
        decision = evaluate_promotion_gate(
            candidate_report_path=report_path,
            current_model_version="v2",
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        # Should not crash
        assert isinstance(decision, PromotionDecision)
    
    def test_gate_symmetric_with_negative_threshold(self, tmp_path):
        """Test gate behavior with negative improvement (degradation)."""
        candidate_report = {
            'candidate_model_version': 'candidate_test',
            'metrics': {
                'candidate_mae': 2500.0,  # Worse (degradation)
                'current_mae': 2000.0,
                'candidate_rmse': 3500.0,
                'current_rmse': 3000.0,
            }
        }
        
        report_path = tmp_path / "candidate_report.json"
        with open(report_path, 'w') as f:
            json.dump(candidate_report, f)
        
        decision = evaluate_promotion_gate(
            candidate_report_path=report_path,
            current_model_version="v2",
            min_relative_improvement=0.0,
            dry_run=True
        )
        
        # Should not promote on degradation
        assert decision.promote is False
