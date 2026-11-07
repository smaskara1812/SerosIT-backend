<#
An alternative to the service: a Windows Task Scheduler task that runs the scheduler ONCE every $EveryMinutes minutes (30 by default: at :00 and :30)
(`python manage.py run_scheduler --once`). Keep -EveryMinutes the same as SCHEDULER_INTERVAL_MINUTES in the .env (30, or 5, 10, 15, 20, 60). Nothing stays running in between and nothing extra needs installing. Run from an elevated PowerShell.

    .\register_scheduler_task.ps1
    .\register_scheduler_task.ps1 -TaskName SerosScheduler -RunAs "SYSTEM"

Remove it with:  schtasks /Delete /TN SerosScheduler /F
Not tested on Windows by the person who wrote it: run it, wait for the next run, then check the Scheduled Mails page.
#>
param(
    [string]$BackendDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$PythonExe = "",
    [string]$TaskName = "SerosScheduler",
    [string]$RunAs = "SYSTEM",
    [int]$EveryMinutes = 30
)
$ErrorActionPreference = "Stop"
if (-not $PythonExe) { $PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe" }
if (-not (Test-Path $PythonExe)) { throw "Python was not found at $PythonExe." }
$cmd = "cmd /c cd /d `"$BackendDir`" && `"$PythonExe`" manage.py run_scheduler --once"
if ($EveryMinutes -notin 5,10,15,20,30,60) { throw "-EveryMinutes must be 5, 10, 15, 20, 30 or 60, so the runs stay on the clock." }
if ($EveryMinutes -eq 60) { schtasks /Create /TN $TaskName /SC HOURLY /ST 00:00 /RU $RunAs /TR $cmd /F }
else { schtasks /Create /TN $TaskName /SC MINUTE /MO $EveryMinutes /ST 00:00 /RU $RunAs /TR $cmd /F }
schtasks /Query /TN $TaskName
Write-Host "Registered. It runs every $EveryMinutes minutes, from 00:00."
