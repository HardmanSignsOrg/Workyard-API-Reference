# Launch the Workyard dashboard (HTTP on :5210 - localhost + Tailscale).
# Uses WorkOrderHub's .venv when present.
#
# Usage:
#   .\run-workyard.ps1
#   .\run-workyard.ps1 --serve-https    # also Tailscale Serve HTTPS for phone camera

# No param() block — so --serve-https is accepted as a raw arg.
$ServeHttps = $false
foreach ($arg in $args) {
    if ($arg -in @('--serve-https', '-serve-https', '-ServeHttps', '/serve-https')) {
        $ServeHttps = $true
    }
}

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = if ($env:WORKYARD_PORT) { [int]$env:WORKYARD_PORT } else { 5210 }

$candidates = @(
    (Join-Path $here '.venv\Scripts\python.exe'),
    (Join-Path $here '..\WorkOrderHub\.venv\Scripts\python.exe'),
    'python'
)
$python = $candidates | Where-Object { $_ -eq 'python' -or (Test-Path $_) } | Select-Object -First 1

function Get-TailscaleExe {
    $paths = @(
        (Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'),
        (Join-Path $env:LocalAppData 'Tailscale\tailscale.exe')
    )
    $pf86 = [Environment]::GetFolderPath('ProgramFilesX86')
    if ($pf86) {
        $paths += (Join-Path $pf86 'Tailscale\tailscale.exe')
    }
    $paths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

function Enable-TailscaleServeHttps {
    param([int]$LocalPort)

    $ts = Get-TailscaleExe
    if (-not $ts) {
        Write-Host 'Tailscale not found - cannot enable --serve-https.' -ForegroundColor Red
        Write-Host "Install Tailscale or open http://127.0.0.1:$LocalPort instead." -ForegroundColor Yellow
        return $null
    }

    Write-Host "Enabling Tailscale Serve -> http://127.0.0.1:$LocalPort ..." -ForegroundColor Cyan
    & $ts serve reset 2>$null | Out-Null
    & $ts serve --bg $LocalPort
    if ($LASTEXITCODE -ne 0) {
        Write-Host "tailscale serve failed (exit $LASTEXITCODE)." -ForegroundColor Red
        return $null
    }

    $dns = $null
    try {
        $json = & $ts status --json 2>$null | Out-String
        $dns = ($json | ConvertFrom-Json).Self.DNSName.TrimEnd('.')
    } catch {
        $dns = $null
    }

    if ($dns) {
        return "https://$dns"
    }
    return 'https://<your-machine>.ts.net  (see: tailscale serve status)'
}

Write-Host "Starting Workyard dashboard with $python" -ForegroundColor Cyan
Write-Host "Local:  http://127.0.0.1:$port" -ForegroundColor Green

if ($ServeHttps) {
    $httpsUrl = Enable-TailscaleServeHttps -LocalPort $port
    if ($httpsUrl) {
        Write-Host "Phone:  $httpsUrl" -ForegroundColor Green
        Write-Host '  Tailscale on phone + this HTTPS URL = rapid in-page camera' -ForegroundColor DarkGray
        Write-Host '  Stop Serve later:  tailscale serve reset' -ForegroundColor DarkGray
    }
} else {
    Write-Host "Phone:  http://<tailscale-ip>:$port   (or re-run with --serve-https)" -ForegroundColor DarkGray
}

& $python (Join-Path $here 'app.py')
