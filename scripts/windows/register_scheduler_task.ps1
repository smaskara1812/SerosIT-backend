<#
An alternative to the service: a Windows Task Scheduler task that runs the scheduler ONCE at the top of every hour
(`python manage.py run_scheduler --once`). Nothing stays running in between and nothing extra needs installing. Run from an elevated PowerShell.

    .\register_scheduler_task.ps1
    .\register_scheduler_task.ps1 -TaskName SerosScheduler -RunAs "SYSTEM"

Remove it with:  schtasks /Delete /TN SerosScheduler /F
Not tested on Windows by the person who wrote it: run it, wait for the next hour, then check the Scheduled Mails page.
#>
param(
    [string]$BackendDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$PythonExe = "",
    [string]$TaskName = "SerosScheduler",
    [string]$RunAs = "SYSTEM"
)
$ErrorActionPreference = "Stop"
if (-not $PythonExe) { $PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe" }
if (-not (Test-Path $PythonExe)) { throw "Python was not found at $PythonExe." }
$cmd = "cmd /c cd /d `"$BackendDir`" && `"$PythonExe`" manage.py run_scheduler --once"
schtasks /Create /TN $TaskName /SC HOURLY /ST 00:00 /RU $RunAs /TR $cmd /F
schtasks /Query /TN $TaskName
Write-Host "Registered. It runs at the top of every hour."
