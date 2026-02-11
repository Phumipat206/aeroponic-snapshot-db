# Cloudflare Tunnel Runner Script
# This script runs cloudflared and captures the URL automatically

param(
    [string]$CloudflaredPath = "cloudflared"
)

$ErrorActionPreference = 'SilentlyContinue'

Write-Host "Starting cloudflared..." -ForegroundColor Cyan

# Start cloudflared process
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $CloudflaredPath
$psi.Arguments = "tunnel --url http://localhost:5000"
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $false

try {
    $process = [System.Diagnostics.Process]::Start($psi)
} catch {
    Write-Host "[ERROR] Failed to start cloudflared: $_" -ForegroundColor Red
    exit 1
}

$tunnelUrl = $null
$timeout = 60
$elapsed = 0

Write-Host "Waiting for tunnel URL..." -ForegroundColor Yellow

while ($elapsed -lt $timeout -and $process -and -not $process.HasExited) {
    Start-Sleep -Milliseconds 500
    $elapsed += 0.5
    
    $output = ""
    try { 
        $output = $process.StandardError.ReadLine() 
    } catch {}
    
    if ($output) {
        Write-Host $output -ForegroundColor DarkGray
        if ($output -match 'https://[a-zA-Z0-9-]+\.trycloudflare\.com') {
            $tunnelUrl = $matches[0]
            break
        }
    }
}

if ($tunnelUrl) {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host "[OK] TUNNEL READY!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Public URL: $tunnelUrl" -ForegroundColor White -BackgroundColor DarkGreen
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Green
    
    # Send URL to Flask API
    try {
        $body = @{url=$tunnelUrl} | ConvertTo-Json
        Invoke-RestMethod -Uri "http://localhost:5000/api/tunnel-url" -Method Post -ContentType "application/json" -Body $body | Out-Null
        Write-Host "[OK] URL sent to web app" -ForegroundColor Green
    } catch {
        Write-Host "[Warning] Could not send URL to web app: $_" -ForegroundColor Yellow
    }
    
    # Open browser
    Start-Process "http://localhost:5000/online"
    
    Write-Host ""
    Write-Host "Browser opened. Press any key to stop the tunnel..." -ForegroundColor Cyan
    [Console]::ReadKey($true) | Out-Null
    
    Write-Host "Stopping tunnel..."
    try {
        $process.Kill()
    } catch {}
    
    exit 0
} else {
    Write-Host "[ERROR] Failed to get tunnel URL within $timeout seconds" -ForegroundColor Red
    if ($process -and -not $process.HasExited) { 
        try { $process.Kill() } catch {}
    }
    exit 1
}
