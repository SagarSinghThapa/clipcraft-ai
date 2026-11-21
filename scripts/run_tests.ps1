# PowerShell automated test runner for ClipCraft AI

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "       ClipCraft AI - Test Suite Runner          " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Check if Python is available in PATH
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue

if (-not $pythonCmd) {
    Write-Host "Python not found in system PATH." -ForegroundColor Yellow
    Write-Host "Please install Python 3.10-3.12 (winget install Python.Python.3.11) or activate your virtual environment." -ForegroundColor Yellow
    exit 1
}

Write-Host "Running comprehensive test suites via python unittest..." -ForegroundColor Green
python tests/run_all_tests.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=================================================" -ForegroundColor Green
    Write-Host "       ALL TEST SUITES PASSED (100% SUCCESS)     " -ForegroundColor Green
    Write-Host "=================================================" -ForegroundColor Green
    exit 0
} else {
    Write-Host ""
    Write-Host "Tests failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}
