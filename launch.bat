@echo off
setlocal EnableExtensions

rem Start backend + frontend in separate terminal windows.
rem Usage: launch.bat

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "ENGINEDIR=%ROOT%\engine"
set "WEBDIR=%ROOT%\web"
set "SCRIPTS=%ROOT%\scripts"

if not exist "%ENGINEDIR%\" (
    echo Engine directory not found: %ENGINEDIR%
    exit /b 1
)
if not exist "%WEBDIR%\" (
    echo Web directory not found: %WEBDIR%
    exit /b 1
)

if not exist "%WEBDIR%\node_modules\" (
    echo Installing web dependencies...
    pushd "%WEBDIR%"
    call npm install
    if errorlevel 1 exit /b 1
    popd
)

echo.
echo Bosch GDPR Discovery Tool
echo   API:  http://127.0.0.1:8000/health
echo   UI:   http://localhost:5173
echo.
echo Opening two terminals:
echo   - GDPR Backend  (FastAPI / uvicorn logs)
echo   - GDPR Frontend (Vite dev server)
echo.
echo Close those windows to stop the servers.
echo.

start "GDPR Backend" cmd /k ""%SCRIPTS%\run-backend.bat""
start "GDPR Frontend" cmd /k ""%SCRIPTS%\run-frontend.bat""

exit /b 0
