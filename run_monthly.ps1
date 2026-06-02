# Monthly trigger for Windows Task Scheduler.
# Sends the statements unattended and appends to runs\YYYY-MM.log.
# Register it to run on the 1st of each month (see README "Schedule it").

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }   # fall back to PATH python

New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "runs") | Out-Null
$stamp = Get-Date -Format "yyyy-MM"
$log = Join-Path $PSScriptRoot "runs\$stamp.log"

"==== run $(Get-Date -Format s) ====" | Out-File -FilePath $log -Append -Encoding utf8
& $py "run.py" "send" "--unattended" *>> $log
"exit code: $LASTEXITCODE" | Out-File -FilePath $log -Append -Encoding utf8
exit $LASTEXITCODE
