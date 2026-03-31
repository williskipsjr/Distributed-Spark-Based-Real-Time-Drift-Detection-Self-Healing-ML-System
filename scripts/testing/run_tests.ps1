# PowerShell Test Runner for Self-Healing ML System
# 
# Usage:
#   .\run_tests_fixed.ps1                    # Run all tests
#   .\run_tests_fixed.ps1 -Profile quick     # Run quick tests only
#   .\run_tests_fixed.ps1 -List              # Show available profiles

param(
    [ValidateSet('all', 'unit', 'integration', 'quick', 'producer', 'model', 'trigger', 'promotion', 'features', 'preprocessing', 'drift', 'retrain', 'spark')]
    [string]$Profile = 'all',
    
    [switch]$Coverage,
    [switch]$Verbose,
    [switch]$ShowOutput,
    [switch]$List
)

$ErrorActionPreference = "Stop"

# Test profiles
$Profiles = @{
    'all' = @{
        'name' = 'All Tests'
        'args' = @()
        'description' = 'Run complete test suite (138 tests)'
    }
    'unit' = @{
        'name' = 'Unit Tests Only'
        'args' = @('-m', 'unit')
        'description' = 'Fast component-level tests'
    }
    'integration' = @{
        'name' = 'Integration Tests'
        'args' = @('-m', 'integration')
        'description' = 'Multi-component workflow tests'
    }
    'quick' = @{
        'name' = 'Quick Unit Tests'
        'args' = @('-m', 'unit', 'and', 'not', 'requires_kafka', 'and', 'not', 'requires_spark')
        'description' = 'Fast tests without external dependencies (~25 sec)'
    }
    'producer' = @{
        'name' = 'Producer Tests'
        'args' = @('tests/test_producer.py', '-v')
        'description' = 'Kafka producer and data loading'
    }
    'model' = @{
        'name' = 'Model Loading Tests'
        'args' = @('tests/test_model_loading.py', '-v')
        'description' = 'Model pointer and loading system'
    }
    'trigger' = @{
        'name' = 'Trigger Tests'
        'args' = @('tests/test_trigger.py', '-v')
        'description' = 'Self-healing trigger decisions'
    }
    'promotion' = @{
        'name' = 'Promotion Tests'
        'args' = @('tests/test_promotion.py', '-v')
        'description' = 'Model promotion gates and rollback'
    }
    'features' = @{
        'name' = 'Feature Engineering Tests'
        'args' = @('tests/test_feature_builder.py', '-v')
        'description' = 'Feature columns and engineering pipeline'
    }
    'preprocessing' = @{
        'name' = 'Data Preprocessing Tests'
        'args' = @('tests/test_offline_preprocess.py', '-v')
        'description' = 'Raw data loading and zone aggregation'
    }
    'drift' = @{
        'name' = 'Drift Detection Tests'
        'args' = @('tests/test_drift_monitor.py', '-v')
        'description' = 'Drift detection and metrics monitoring'
    }
    'retrain' = @{
        'name' = 'Retraining Pipeline Tests'
        'args' = @('tests/test_retrain_pipeline.py', '-v')
        'description' = 'Model retraining and candidate generation'
    }
    'spark' = @{
        'name' = 'Spark Streaming Tests'
        'args' = @('tests/test_spark_job.py', '-v')
        'description' = 'Spark streaming job and metrics pipeline'
    }
}

function Show-Profiles {
    Write-Host "`n📋 Available Test Profiles:`n" -ForegroundColor Cyan
    foreach ($name in $Profiles.Keys | Sort-Object) {
        $desc = $Profiles[$name]['description']
        Write-Host "  $($name.PadRight(15)) - $desc"
    }
    Write-Host ""
}

function Run-Tests {
    param($ProfileName, $Coverage, $Verbose, $ShowOutput)
    
    # Validate profile
    if (-not $Profiles.ContainsKey($ProfileName)) {
        Write-Host "❌ Unknown profile: $ProfileName" -ForegroundColor Red
        Show-Profiles
        return 1
    }
    
    # Get profile config
    $config = $Profiles[$ProfileName]
    Write-Host "`n$('='*60)" -ForegroundColor Green
    Write-Host "▶ $($config['name'])" -ForegroundColor Green
    Write-Host "  $($config['description'])" -ForegroundColor Gray
    Write-Host "$('='*60)`n" -ForegroundColor Green
    
    # Build command
    $cmd = @('python', '-m', 'pytest')
    
    # Add coverage if requested
    if ($Coverage) {
        $cmd += @('--cov=src', '--cov-report=html', '--cov-report=term-missing')
    }
    
    # Add verbosity
    if ($Verbose) {
        $cmd += @('-vv', '--tb=long')
    } else {
        $cmd += @('-v', '--tb=short')
    }
    
    # Add show output flag
    if ($ShowOutput) {
        $cmd += '-s'
    }
    
    # Add profile-specific args
    $cmd += $config['args']
    
    # Run tests
    try {
        & $cmd[0] $cmd[1..($cmd.Count - 1)]
        $exitCode = $LASTEXITCODE
        
        if ($exitCode -eq 0) {
            Write-Host "`n$('='*60)" -ForegroundColor Green
            Write-Host "✓ Tests PASSED" -ForegroundColor Green
            Write-Host "$('='*60)`n" -ForegroundColor Green
            
            if ($Coverage) {
                Write-Host "📊 Coverage report: htmlcov/index.html`n" -ForegroundColor Cyan
            }
        } else {
            Write-Host "`n$('='*60)" -ForegroundColor Red
            Write-Host "✗ Tests FAILED" -ForegroundColor Red
            Write-Host "$('='*60)`n" -ForegroundColor Red
        }
        
        return $exitCode
    }
    catch {
        Write-Host "❌ Error running tests: $_" -ForegroundColor Red
        return 1
    }
}

# Main logic
if ($List) {
    Show-Profiles
    exit 0
}

Run-Tests -ProfileName $Profile -Coverage $Coverage -Verbose $Verbose -ShowOutput $ShowOutput
exit $LASTEXITCODE
