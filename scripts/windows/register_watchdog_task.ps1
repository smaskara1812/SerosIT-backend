<#
Registers the scheduler WATCHDOG: a Windows Task Scheduler task that runs `python manage.py check_scheduler_health` every 15 minutes.
It looks at the scheduler service's heartbeat, mail that is overdue and the mail server, records problems, and e-mails SCHEDULER_ERROR_MAIL_TO once per
problem (only when SCHEDULER_HEALTH_ALERTS=True in .env). It is not a service: it starts, checks and exits. Run from an elevated PowerShell.

    .\register_watchdog_task.ps1
    .\register_watchdog_task.ps1 -TaskName SerosWatchdog -EveryMinutes 15 -RunAs "SYSTEM"

Remove it with:  .\unregister_watchdog_task.ps1
Not tested on Windows by the person who wrote it: run it, then `schtasks /Run /TN SerosWatchdog` and check the Scheduled Mails page.
#>
param(
    [string]$BackendDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$PythonExe = "",
    [string]$TaskName = "SerosWatchdog",
    [int]$EveryMinutes = 15,
    [string]$RunAs = "SYSTEM"
)
$ErrorActionPreference = "Stop"
if (-not $PythonExe) { $PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe" }
if (-not (Test-Path $PythonExe)) { throw "Python was not found at $PythonExe." }
$cmd = "cmd /c cd /d `"$BackendDir`" && `"$PythonExe`" manage.py check_scheduler_health"
schtasks /Create /TN $TaskName /SC MINUTE /MO $EveryMinutes /ST 00:00 /RU $RunAs /TR $cmd /F
schtasks /Query /TN $TaskName
Write-Host "Registered. It runs every $EveryMinutes minutes."
