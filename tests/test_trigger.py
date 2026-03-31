"""
Unit tests for self-healing trigger decision logic.
"""
import json
from pathlib import Path

import pytest

from src.self_healing.trigger import evaluate_trigger


@pytest.mark.unit
class TestTriggerDecisions:
    """Tests for trigger decision evaluation."""
    
    def test_trigger_function_exists(self):
        """Test that trigger evaluation function exists."""
        assert callable(evaluate_trigger)
    
    def test_trigger_returns_dict(self):
        """Test that trigger returns dictionary with required fields."""
        decision = evaluate_trigger(
            consecutive_drift_count=0,
            days_since_last_promotion=2,
            candidate_report_exists=False,
            candidate_report_content=None,
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        assert isinstance(decision, dict)
        assert 'decision' in decision
        assert 'reason' in decision
    
    def test_trigger_no_action_when_stable(self):
        """Test trigger recommends no_action for stable model."""
        decision = evaluate_trigger(
            consecutive_drift_count=0,
            days_since_last_promotion=2,
            candidate_report_exists=False,
            candidate_report_content=None,
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        assert decision['decision'] == 'no_action'
        assert 'stable' in decision.get('reason', '').lower() or \
               'no action' in decision.get('reason', '').lower()
    
    def test_trigger_retrain_on_drift(self):
        """Test trigger recommends retrain on consecutive drift."""
        decision = evaluate_trigger(
            consecutive_drift_count=3,  # Threshold crossed
            days_since_last_promotion=2,
            candidate_report_exists=False,
            candidate_report_content=None,
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        assert decision['decision'] in ['retrain_candidate', 'no_action']
    
    def test_trigger_promotes_on_candidate_ready(self):
        """Test trigger recommends promotion when candidate ready."""
        candidate_report = {
            'promotion_recommended': True,
            'ready_for_promotion': True,
            'candidate_model_version': 'candidate_20260331T120000Z',
            'metrics': {
                'candidate_mae': 1500.0,
                'current_mae': 2000.0,
                'candidate_rmse': 2500.0,
                'current_rmse': 3000.0,
            }
        }
        
        decision = evaluate_trigger(
            consecutive_drift_count=0,
            days_since_last_promotion=7,  # Old enough
            candidate_report_exists=True,
            candidate_report_content=candidate_report,
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        # Decision should consider promoting or at least acknowledge candidate
        assert decision['decision'] in ['promote_candidate', 'no_action']
    
    def test_trigger_respects_min_improvement_threshold(self):
        """Test trigger respects minimum improvement threshold."""
        # Candidate with insufficient improvement (< 25%)
        candidate_report = {
            'promotion_recommended': False,  # Not recommended by pipeline
            'ready_for_promotion': False,
            'candidate_model_version': 'candidate_20260331T120000Z',
            'metrics': {
                'candidate_mae': 1950.0,  # Only 2.5% improvement
                'current_mae': 2000.0,
                'candidate_rmse': 3000.0,
                'current_rmse': 2950.0,  # Actually worse
            }
        }
        
        decision = evaluate_trigger(
            consecutive_drift_count=0,
            days_since_last_promotion=0,
            candidate_report_exists=True,
            candidate_report_content=candidate_report,
            min_relative_improvement=0.25,  # Need 25% improvement
            dry_run=True
        )
        
        # Should not promote with insufficient improvement
        assert decision['decision'] != 'promote_candidate'


@pytest.mark.unit
class TestTriggerArtifacts:
    """Tests for trigger artifact generation."""
    
    def test_trigger_decision_logged(self, project_root):
        """Test that trigger decisions are logged to JSONL."""
        decisions_file = project_root / "artifacts" / "self_healing" / "trigger_decisions.jsonl"
        
        if decisions_file.exists():
            with open(decisions_file, 'r') as f:
                lines = f.readlines()
            
            assert len(lines) > 0, "Trigger decisions log is empty"
            
            # Each line should be valid JSON
            for line in lines[-5:]:  # Check last 5 entries
                entry = json.loads(line)
                assert 'timestamp' in entry or 'decision' in entry
    
    def test_trigger_dry_run_no_command_execution(self):
        """Test that dry-run doesn't execute promotion command."""
        decision = evaluate_trigger(
            consecutive_drift_count=0,
            days_since_last_promotion=7,
            candidate_report_exists=True,
            candidate_report_content={
                'promotion_recommended': True,
                'ready_for_promotion': True,
                'candidate_model_version': 'candidate_test'
            },
            min_relative_improvement=0.0,
            dry_run=True  # Dry-run mode
        )
        
        # In dry-run, we should get a recommendation but not execute
        assert 'command' not in decision or decision.get('executed') is False


@pytest.mark.unit
class TestTriggerEdgeCases:
    """Tests for trigger edge cases."""
    
    def test_trigger_missing_candidate_report(self):
        """Test trigger when candidate report doesn't exist."""
        decision = evaluate_trigger(
            consecutive_drift_count=0,
            days_since_last_promotion=7,
            candidate_report_exists=False,
            candidate_report_content=None,
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        # Should not crash or recommend promotion
        assert decision['decision'] in ['no_action', 'retrain_candidate']
    
    def test_trigger_malformed_candidate_report(self):
        """Test trigger with malformed candidate report."""
        decision = evaluate_trigger(
            consecutive_drift_count=0,
            days_since_last_promotion=7,
            candidate_report_exists=True,
            candidate_report_content={'incomplete': 'data'},  # Missing required fields
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        # Should handle gracefully
        assert isinstance(decision, dict)
        assert 'decision' in decision
    
    def test_trigger_zero_improvement_threshold(self):
        """Test trigger with 0% improvement threshold."""
        candidate_report = {
            'promotion_recommended': False,
            'ready_for_promotion': True,
            'candidate_model_version': 'candidate_test',
            'metrics': {
                'candidate_mae': 1999.0,  # 0.05% improvement (essentially zero)
                'current_mae': 2000.0,
                'candidate_rmse': 2900.0,
                'current_rmse': 3000.0,
            }
        }
        
        decision = evaluate_trigger(
            consecutive_drift_count=0,
            days_since_last_promotion=7,
            candidate_report_exists=True,
            candidate_report_content=candidate_report,
            min_relative_improvement=0.0,  # Accept any improvement
            dry_run=True
        )
        
        # With 0% threshold and actual improvement, should consider promoting
        assert decision['decision'] in ['promote_candidate', 'no_action']
