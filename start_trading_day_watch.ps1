$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $workspace "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir ("trading_watch_" + (Get-Date -Format "yyyyMMdd") + ".log")

function Write-Log($message) {
    $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] " + $message
    Add-Content -Path $logPath -Value $line -Encoding UTF8
}

$today = Get-Date
$dateText = $today.ToString("yyyy-MM-dd")
$dayOfWeek = $today.DayOfWeek

if ($dayOfWeek -eq "Saturday" -or $dayOfWeek -eq "Sunday") {
    Write-Log "Skip: weekend."
    exit 0
}

$holidayPath = Join-Path $workspace "a_share_holidays_2026.txt"
$holidays = @()
if (Test-Path $holidayPath) {
    $holidays = Get-Content $holidayPath | Where-Object {
        $_ -and -not $_.Trim().StartsWith("#")
    } | ForEach-Object { $_.Trim() }
}

if ($holidays -contains $dateText) {
    Write-Log "Skip: A-share market holiday."
    exit 0
}

Write-Log "Start watch."
Set-Location $workspace
Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $workspace "run_screen_observer.ps1"),
    "--watch"
)
Write-Log "Auction watch launched."

$openingStart = Get-Date -Hour 9 -Minute 29 -Second 40
while ((Get-Date) -lt $openingStart) {
    Start-Sleep -Seconds 1
}

Write-Log "Start opening momentum watch. Please keep the watched region on speed-gainer list."
& powershell -NoProfile -ExecutionPolicy Bypass -File ".\run_opening_momentum.ps1" *>> $logPath
Write-Log "Opening momentum watch finished."
