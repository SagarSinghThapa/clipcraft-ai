# PowerShell startup script for ClipCraft AI

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "                ClipCraft AI - Startup Launcher            " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python & Virtual Environment
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$pyExec = $null

if (Test-Path $venvPython) {
    $pyExec = $venvPython
    $verOut = & $pyExec --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Virtual Environment Python: $verOut ($pyExec)" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] .venv Python failed execution: $verOut" -ForegroundColor Yellow
        $pyExec = $null
    }
}

if (-not $pyExec) {
    $sysPython = Get-Command python -ErrorAction SilentlyContinue
    if ($sysPython) {
        $verOut = & python --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $verOut -match "Python \d") {
            $pyExec = "python"
            Write-Host "[OK] System Python detected: $verOut" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] System python command returned error or Windows Store stub." -ForegroundColor Yellow
        }
    }
}

if (-not $pyExec) {
    Write-Host "[ERROR] Valid Python installation not found!" -ForegroundColor Red
    Write-Host "        Please install Python 3.10-3.12 or initialize .venv" -ForegroundColor Red
    exit 1
}

# 2. Check Node.js & npm
$nodeVer = & node --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Node.js detected: $nodeVer" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Node.js not detected on system PATH." -ForegroundColor Yellow
}

# 3. Check FFmpeg
$ffmpegVer = & ffmpeg -version 2>&1
if ($LASTEXITCODE -eq 0) {
    $firstLine = ($ffmpegVer -split "`r?`n")[0]
    Write-Host "[OK] FFmpeg detected: $firstLine" -ForegroundColor Green
} else {
    Write-Host "[WARNING] FFmpeg not detected on system PATH." -ForegroundColor Yellow
    Write-Host "          Install FFmpeg via: winget install Gyan.FFmpeg" -ForegroundColor Yellow
}

# 4. Check yt-dlp
$ytdlpVer = & $pyExec -m yt_dlp --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] yt-dlp detected: $ytdlpVer" -ForegroundColor Green
} else {
    Write-Host "[WARNING] yt-dlp not available in Python environment. Run: $pyExec -m pip install yt-dlp" -ForegroundColor Yellow
}

# 5. Check Ollama
$ollamaVer = & ollama --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Ollama detected: $ollamaVer" -ForegroundColor Green
} else {
    Write-Host "[INFO] Ollama CLI not found in PATH." -ForegroundColor Gray
    Write-Host "       Install from https://ollama.com for local AI highlight discovery." -ForegroundColor Gray
}

Write-Host ""
Write-Host "Starting ClipCraft AI services..." -ForegroundColor Cyan

# Launch backend FastAPI in background
Write-Host "Starting Backend API on http://127.0.0.1:8000..." -ForegroundColor White
$backendJob = Start-Process $pyExec -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload" -PassThru

# Launch frontend Vite in background
Write-Host "Starting Frontend UI on http://localhost:5173..." -ForegroundColor White
$frontendJob = Start-Process npm -ArgumentList "run", "dev" -WorkingDirectory (Join-Path $PSScriptRoot "frontend") -PassThru

# Verify service health before reporting running
Write-Host "Verifying backend health..." -NoNewline
$backendReady = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -ErrorAction Stop
        if ($resp.status -eq "healthy") {
            $backendReady = $true
            break
        }
    } catch {
        Write-Host "." -NoNewline
    }
}
Write-Host ""

if ($backendReady) {
    Write-Host "[OK] Backend API is healthy and responding!" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Backend API did not respond within 15 seconds. Check backend logs." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "   ClipCraft AI is RUNNING: http://localhost:5173         " -ForegroundColor Green
Write-Host "   Backend API Docs:        http://127.0.0.1:8000/docs    " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Press Ctrl+C or close this terminal window to stop." -ForegroundColor Gray

# Wait for jobs
try {
    $backendJob.WaitForExit()
} finally {
    if ($backendJob -and -not $backendJob.HasExited) { Stop-Process -Id $backendJob.Id -Force }
    if ($frontendJob -and -not $frontendJob.HasExited) { Stop-Process -Id $frontendJob.Id -Force }
}
