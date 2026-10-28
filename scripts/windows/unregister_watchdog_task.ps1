<# Removes the scheduler watchdog task (registered by register_watchdog_task.ps1). Run from an elevated PowerShell. #>
param([string]$TaskName = "SerosWatchdog")
$ErrorActionPreference = "Stop"
schtasks /Delete /TN $TaskName /F
Write-Host "Removed $TaskName."
