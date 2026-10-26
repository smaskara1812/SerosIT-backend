<#
Installs the SerosIT scheduler as a Windows service, using NSSM (the Non-Sucking Service Manager, a free single-file tool: https://nssm.cc).
Run it from an elevated PowerShell (Run as administrator) on the server, once.

    .\install_scheduler_service.ps1
    .\install_scheduler_service.ps1 -NssmPath C:\Tools\nssm.exe -ServiceUser "DOMAIN\svc-seros" -ServicePassword "..."

What the service does: `python manage.py run_scheduler`, which runs once when it starts and then at the top of every hour, and looks after every
automatic mail the system has (the Birthday Mailer today). It reads the same `.env` as the web application (it starts in the backend folder), restarts
itself a minute after any crash, and writes its own output to backend\logs\service.out.log and service.err.log. The scheduler's own log is
backend\logs\scheduler-<date>.log, and every error also goes to automation_errors-<date>.log.

Not tested on Windows by the person who wrote it: run it, then check the Scheduled Mails page (it shows when the scheduler last ran).
#>
param(
    [string]$BackendDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$PythonExe = "",
    [string]$ServiceName = "SerosScheduler",
    [string]$NssmPath = "nssm.exe",
    [string]$ServiceUser = "",
    [string]$ServicePassword = ""
)
$ErrorActionPreference = "Stop"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this from an elevated PowerShell (Run as administrator)."
}
if (-not $PythonExe) { $PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe" }
if (-not (Test-Path $PythonExe)) { throw "Python was not found at $PythonExe. Pass -PythonExe with the path to the virtual environment's python.exe." }
if (-not (Test-Path (Join-Path $BackendDir "manage.py"))) { throw "manage.py was not found in $BackendDir." }
if (-not (Get-Command $NssmPath -ErrorAction SilentlyContinue) -and -not (Test-Path $NssmPath)) {
    throw "nssm.exe was not found. Download it from https://nssm.cc, put it somewhere on the PATH (or pass -NssmPath), and run this again. Or use register_scheduler_task.ps1 instead."
}
$logs = Join-Path $BackendDir "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

if (& $NssmPath status $ServiceName 2>$null) {
    Write-Host "The service $ServiceName already exists: stopping and removing it first."
    & $NssmPath stop $ServiceName | Out-Null
    & $NssmPath remove $ServiceName confirm | Out-Null
}

& $NssmPath install $ServiceName $PythonExe "manage.py" "run_scheduler"
& $NssmPath set $ServiceName AppDirectory $BackendDir
& $NssmPath set $ServiceName DisplayName "SerosIT Scheduler"
& $NssmPath set $ServiceName Description "Sends the automatic mails (the Birthday Mailer and others) once an hour on the hour."
& $NssmPath set $ServiceName Start SERVICE_AUTO_START
& $NssmPath set $ServiceName AppStdout (Join-Path $logs "service.out.log")
& $NssmPath set $ServiceName AppStderr (Join-Path $logs "service.err.log")
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateOnline 1
& $NssmPath set $ServiceName AppRotateBytes 10485760
& $NssmPath set $ServiceName AppExit Default Restart
& $NssmPath set $ServiceName AppRestartDelay 60000
& $NssmPath set $ServiceName AppStopMethodConsole 15000
if ($ServiceUser) { & $NssmPath set $ServiceName ObjectName $ServiceUser $ServicePassword }

& $NssmPath start $ServiceName
Start-Sleep -Seconds 5
& $NssmPath status $ServiceName
Write-Host ""
Write-Host "Installed. Open Admin > Scheduled Mails: it should say the scheduler is running. Logs: $logs"
