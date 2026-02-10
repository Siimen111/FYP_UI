$ErrorActionPreference = "Stop"

function Test-FastApiRunning {
  $processes = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%.exe'"
  foreach ($proc in $processes) {
    if ($proc.CommandLine -match "uvicorn vtrack\.api:app") {
      return $true
    }
  }
  return $false
}

function Start-FastApi {
  if (Test-FastApiRunning) {
    Write-Host "FastAPI server already running."
    return
  }

  $env:VTRACK_DEVICE_MAP = "auto"
  $env:VTRACK_MAX_NEW_TOKENS = "128"
  $env:VTRACK_BASE_MODEL = "C:\Users\sherm\FYP\src\gemma_3_4b_it"

  $root = Split-Path -Parent $PSScriptRoot
  $src = Join-Path $root "src"
  Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$src`"; python -m uvicorn vtrack.api:app"
  )
}

function Start-LawyerUi {
  $root = Split-Path -Parent $PSScriptRoot
  $desktop = Join-Path $root "desktop"
  Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$desktop`"; & nvm on; Start-Sleep -Seconds 2; & npm run start:lawyer"
  )
}

Start-FastApi
Start-LawyerUi
