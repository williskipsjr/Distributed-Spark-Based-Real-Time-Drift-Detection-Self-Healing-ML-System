#!/usr/bin/env python3
"""
Test runner script for Self-Healing ML System.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --unit             # Run unit tests only
    python run_tests.py --integration      # Run integration tests
    python run_tests.py --quick            # Run fast unit tests
    python run_tests.py --coverage         # Run with coverage report
    python run_tests.py --debug TestClass::test_method  # Debug single test
"""
import subprocess
import sys
from pathlib import Path


class TestRunner:
    """Test orchestration for the ML system."""

    # ----------------------------------------------------
    # ---------------- Test Profile Matrix ---------------
    # Named pytest profiles used by CLI flags below.
    # ----------------------------------------------------
    PROFILES = {
        'all': {
            'name': 'All Tests',
            'args': [],
            'description': 'Run complete test suite (150+ tests)'
        },
        'unit': {
            'name': 'Unit Tests Only',
            'args': ['-m', 'unit'],
            'description': 'Fast component-level tests'
        },
        'integration': {
            'name': 'Integration Tests',
            'args': ['-m', 'integration'],
            'description': 'Multi-component workflow tests'
        },
        'quick': {
            'name': 'Quick Unit Tests',
            'args': ['-m', 'unit', 'and', 'not', 'requires_kafka', 'and', 'not', 'requires_spark'],
            'description': 'Fast tests without external dependencies'
        },
        'producer': {
            'name': 'Producer Tests',
            'args': ['tests/test_producer.py', '-v'],
            'description': 'Kafka producer and data loading'
        },
        'model': {
            'name': 'Model Loading Tests',
            'args': ['tests/test_model_loading.py', '-v'],
            'description': 'Model pointer and loading system'
        },
        'trigger': {
            'name': 'Trigger Tests',
            'args': ['tests/test_trigger.py', '-v'],
            'description': 'Self-healing trigger decisions'
        },
        'promotion': {
            'name': 'Promotion Tests',
            'args': ['tests/test_promotion.py', '-v'],
            'description': 'Model promotion gates and rollback (14 tests)'
        },
        'features': {
            'name': 'Feature Engineering Tests',
            'args': ['tests/test_feature_builder.py', '-v'],
            'description': 'Feature engineering pipeline (20 tests)'
        },
        'preprocessing': {
            'name': 'Data Preprocessing Tests',
            'args': ['tests/test_offline_preprocess.py', '-v'],
            'description': 'Offline data preprocessing (18 tests)'
        },
        'drift': {
            'name': 'Drift Detection Tests',
            'args': ['tests/test_drift_monitor.py', '-v'],
            'description': 'Drift detection and monitoring (20 tests)'
        },
        'retrain': {
            'name': 'Retraining Pipeline Tests',
            'args': ['tests/test_retrain_pipeline.py', '-v'],
            'description': 'Model retraining and candidate generation (22 tests)'
        },
        'spark': {
            'name': 'Spark Streaming Tests',
            'args': ['tests/test_spark_job.py', '-v'],
            'description': 'Spark streaming job and inference (18 tests)'
        },
    }
    
    @staticmethod
    def run(profile='all', extra_args=None, coverage=False, verbose=False):
        """Run tests with specified profile."""
        # Build a deterministic pytest command from selected profile.
        if profile not in TestRunner.PROFILES:
            print(f"❌ Unknown profile: {profile}")
            print(f"Available profiles: {', '.join(TestRunner.PROFILES.keys())}")
            sys.exit(1)
        
        config = TestRunner.PROFILES[profile]
        print(f"\n{'='*60}")
        print(f"▶ {config['name']}")
        print(f"  {config['description']}")
        print(f"{'='*60}\n")
        
        # Build command
        cmd = ['pytest']
        
        if coverage:
            cmd.extend(['--cov=src', '--cov-report=html', '--cov-report=term-missing'])
        
        if verbose:
            cmd.extend(['-vv', '--tb=long'])
        else:
            cmd.extend(['-v', '--tb=short'])
        
        # Add profile-specific args
        cmd.extend(config['args'])
        
        # Add extra args
        if extra_args:
            cmd.extend(extra_args)
        
        # Run tests
        try:
            result = subprocess.run(cmd, cwd=Path(__file__).parent)
            
            if result.returncode == 0:
                print(f"\n{'='*60}")
                print(f"✓ {config['name']} PASSED")
                print(f"{'='*60}\n")
                
                if coverage:
                    print("Coverage report: htmlcov/index.html")
            else:
                print(f"\n{'='*60}")
                print(f"✗ {config['name']} FAILED")
                print(f"{'='*60}\n")
            
            return result.returncode
        
        except FileNotFoundError:
            print("❌ pytest not found. Install with: pip install pytest")
            sys.exit(1)
    
    @staticmethod
    def list_profiles():
        """List available test profiles."""
        print("\n📋 Available Test Profiles:\n")
        for name, config in TestRunner.PROFILES.items():
            print(f"  {name:15} - {config['description']}")
        print()


def main():
    """Main entry point."""
    import argparse

    # ----------------------------------------------------
    # ---------------- CLI Argument Parser ---------------
    # Maps user-friendly flags to pre-defined test profiles.
    # ----------------------------------------------------
    parser = argparse.ArgumentParser(
        description='Test runner for Self-Healing ML System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python run_tests.py                    # Run all tests
  python run_tests.py --unit             # Run unit tests only
  python run_tests.py --quick            # Run fast unit tests
  python run_tests.py --producer         # Test data producer
  python run_tests.py --coverage         # Generate coverage report
  python run_tests.py --unit --verbose   # Verbose unit tests
  python run_tests.py --trigger -s       # Show print statements
        '''
    )
    
    # Profiles
    for name, config in TestRunner.PROFILES.items():
        parser.add_argument(
            f'--{name}',
            action='store_true',
            help=config['description']
        )
    
    # Options
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--verbose', '-vv', action='store_true', help='Verbose output')
    parser.add_argument('-s', '--show-output', action='store_true', help='Show print statements')
    parser.add_argument('--debug', type=str, help='Debug specific test: TestClass::test_method')
    parser.add_argument('--list', action='store_true', help='List available profiles')
    
    args = parser.parse_args()
    
    # List profiles
    if args.list:
        TestRunner.list_profiles()
        return 0
    
    # Determine profile
    profile = 'all'
    for name in TestRunner.PROFILES.keys():
        if getattr(args, name, False):
            profile = name
            break
    
    # Build extra args
    extra_args = []
    if args.show_output:
        extra_args.append('-s')
    
    if args.debug:
        profile = 'debug'
        extra_args = [f'tests/{args.debug}', '-vv', '-s']
    
    # Run tests
    return TestRunner.run(
        profile=profile,
        extra_args=extra_args if extra_args else None,
        coverage=args.coverage,
        verbose=args.verbose
    )


if __name__ == '__main__':
    sys.exit(main())
