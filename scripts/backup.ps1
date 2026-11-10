<#
.SYNOPSIS
    Callwise Automated Database Backup Script (PowerShell)
#>
param(
    [string]$OutputDir = "backups"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$Timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
Write-Host "=== Callwise Database Backup (PowerShell) ==="
Write-Host "Target Directory: $OutputDir"

try {
    uv run python -m callwise.cli db backup --output-dir "$OutputDir"
    Write-Host "[OK] Backup completed successfully." -ForegroundColor Green
} catch {
    Write-Error "Backup failed: $_"
    exit 1
}

