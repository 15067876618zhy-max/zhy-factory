$ErrorActionPreference = "Stop"

$python = Get-Command python -ErrorAction SilentlyContinue
$runtimePython = "C:\Users\29454\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if ($python -and $python.Source -notlike "*WindowsApps*") {
    & $python.Source screen_observer.py @args
} elseif (Test-Path $runtimePython) {
    & $runtimePython screen_observer.py @args
} else {
    Write-Host "No usable Python was found. Please install Python or use the Codex bundled runtime."
    exit 1
}
