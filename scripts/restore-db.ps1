<#
.SYNOPSIS
    Callwise Automated Database Restore Script (PowerShell)
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupFile)) {
    Write-Error "Backup file '$BackupFile' does not exist."
    exit 1
}

Write-Host "=== Callwise Database Restore (PowerShell) ==="
Write-Host "Restoring from: $BackupFile"

try {
    uv run python -m callwise.cli db restore "$BackupFile"
    Write-Host "[OK] Restore completed successfully." -ForegroundColor Green
} catch {
    Write-Error "Restore failed: $_"
    exit 1
}

