# Launch the Workyard dashboard (http://localhost:5210).
# Uses WorkOrderHub's .venv (has flask/requests/dotenv); falls back to a local
# .venv or system python if present.

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidates = @(
    (Join-Path $here '.venv\Scripts\python.exe'),
    (Join-Path $here '..\WorkOrderHub\.venv\Scripts\python.exe'),
    'python'
)
$python = $candidates | Where-Object { $_ -eq 'python' -or (Test-Path $_) } | Select-Object -First 1

Write-Host "Starting Workyard dashboard with $python" -ForegroundColor Cyan
Write-Host "-> http://localhost:5210" -ForegroundColor Green
& $python (Join-Path $here 'app.py')
