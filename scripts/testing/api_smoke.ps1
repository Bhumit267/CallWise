# Fast API Smoke Verification Script for Callwise Backend
# Tests /health, owner authentication, and basic data retrieval.

$ErrorActionPreference = "Stop"
$API_BASE = "http://localhost:8000"

Write-Host "=== Callwise API Smoke Test ===" -ForegroundColor Cyan

# 1. Health check
Write-Host "1. Checking GET /health ..." -NoNewline
try {
    $health = Invoke-RestMethod -Uri "$API_BASE/health" -Method Get -TimeoutSec 5
    if ($health.status -eq "healthy") {
        Write-Host " [PASS] (Status: $($health.status), DB: $($health.components.database.status))" -ForegroundColor Green
    } else {
        Write-Host " [WARN] (Status: $($health.status))" -ForegroundColor Yellow
    }
} catch {
    Write-Host " [FAIL]: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 2. Authentication Login
Write-Host "2. Authenticating as dental.owner@test.com ..." -NoNewline
$loginBody = @{
    email = "dental.owner@test.com"
    password = "Password123!"
} | ConvertTo-Json

try {
    $webSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $authResp = Invoke-RestMethod -Uri "$API_BASE/api/auth/login" -Method Post -Body $loginBody -ContentType "application/json" -WebSession $webSession
    Write-Host " [PASS] (User: $($authResp.user.name), Business: $($authResp.current_business.name))" -ForegroundColor Green
} catch {
    Write-Host " [FAIL]: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 3. Read current user profile
Write-Host "3. Verifying GET /api/auth/me ..." -NoNewline
try {
    $meResp = Invoke-RestMethod -Uri "$API_BASE/api/auth/me" -Method Get -WebSession $webSession
    if ($meResp.user.email -eq "dental.owner@test.com") {
        Write-Host " [PASS] (Role: $($meResp.current_business.role))" -ForegroundColor Green
    } else {
        Write-Host " [FAIL] Unexpected email: $($meResp.user.email)" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host " [FAIL]: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 4. Read appointments
Write-Host "4. Querying GET /api/appointments ..." -NoNewline
try {
    $appts = Invoke-RestMethod -Uri "$API_BASE/api/appointments" -Method Get -WebSession $webSession
    Write-Host " [PASS] ($($appts.Count) appointments returned)" -ForegroundColor Green
} catch {
    Write-Host " [FAIL]: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "=== All API Smoke Checks Passed Successfully! ===" -ForegroundColor Green
