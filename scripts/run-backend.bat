@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PYTHON="
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON if exist "%ROOT%\engine\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\engine\.venv\Scripts\python.exe"
if not defined PYTHON set "PYTHON=python"

set "ENGINEDIR=%ROOT%\engine"
set "PYTHONPATH=%ENGINEDIR%"

set "YOLO=%ROOT%\data\models\yolov8n.pt"
if exist "%YOLO%" set "GDPR_YOLO_WEIGHTS=%YOLO%"

set "API_PORT=8000"
if defined GDPR_API_PORT set "API_PORT=%GDPR_API_PORT%"

title GDPR Backend
echo Bosch GDPR Scan Engine
echo   API: http://127.0.0.1:%API_PORT%/health
if defined GDPR_YOLO_WEIGHTS echo   YOLO: %GDPR_YOLO_WEIGHTS%
echo.

rem Free the port if a previous backend is still listening (avoids WinError 10013).
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%API_PORT% " ^| findstr "LISTENING"') do (
  if not "%%P"=="0" (
    echo Stopping process on port %API_PORT% ^(PID %%P^)...
    taskkill /PID %%P /F >nul 2>&1
  )
)
ping -n 2 127.0.0.1 >nul

cd /d "%ENGINEDIR%"
"%PYTHON%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port %API_PORT%
