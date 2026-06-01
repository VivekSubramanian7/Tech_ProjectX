# Start the full Bosch GDPR Discovery tool in two separate terminal windows.

# Usage: .\launch.ps1



$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot

$Scripts = Join-Path $Root "scripts"



function Resolve-Python {

    $candidates = @(

        (Join-Path $Root ".venv\Scripts\python.exe"),

        (Join-Path $Root "engine\.venv\Scripts\python.exe")

    )

    foreach ($candidate in $candidates) {

        if (Test-Path $candidate) {

            return $candidate

        }

    }

    return "python"

}



$engineDir = Join-Path $Root "engine"

$webDir = Join-Path $Root "web"



if (-not (Test-Path $engineDir)) {

    throw "Engine directory not found: $engineDir"

}

if (-not (Test-Path $webDir)) {

    throw "Web directory not found: $webDir"

}



if (-not (Test-Path (Join-Path $webDir "node_modules"))) {

    Write-Host "Installing web dependencies..."

    Push-Location $webDir

    try {

        npm install

    } finally {

        Pop-Location

    }

}



Write-Host ""

Write-Host "Bosch GDPR Discovery Tool"

Write-Host "  API:  http://127.0.0.1:8000/health"

Write-Host "  UI:   http://localhost:5173"

Write-Host ""

Write-Host "Opening two terminals:"

Write-Host "  - GDPR Backend  (FastAPI / uvicorn logs)"

Write-Host "  - GDPR Frontend (Vite dev server)"

Write-Host ""

Write-Host "Close those windows to stop the servers."

Write-Host ""



$backendBat = Join-Path $Scripts "run-backend.bat"

$frontendBat = Join-Path $Scripts "run-frontend.bat"



Start-Process cmd.exe -ArgumentList @("/k", "`"$backendBat`"")

Start-Process cmd.exe -ArgumentList @("/k", "`"$frontendBat`"")


