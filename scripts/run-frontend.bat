@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "WEBDIR=%ROOT%\web"

if not exist "%WEBDIR%\node_modules\" (
    echo Installing web dependencies...
    pushd "%WEBDIR%"
    call npm install
    if errorlevel 1 exit /b 1
    popd
)

title GDPR Frontend
echo Bosch GDPR Web UI
echo   UI: http://localhost:5173
echo.

cd /d "%WEBDIR%"
call npm run dev
