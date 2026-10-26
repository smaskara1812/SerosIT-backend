<# Stops and removes the SerosIT scheduler service (installed by install_scheduler_service.ps1). Run from an elevated PowerShell. #>
param([string]$ServiceName = "SerosScheduler", [string]$NssmPath = "nssm.exe")
$ErrorActionPreference = "Stop"
& $NssmPath stop $ServiceName
& $NssmPath remove $ServiceName confirm
Write-Host "Removed $ServiceName."
