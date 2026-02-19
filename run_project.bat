@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

if not exist logs mkdir logs

echo [1/4] Checking Python launcher...
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher "py" was not found.
  echo Install Python 3.12, then run this file again.
  exit /b 1
)

echo [2/4] Freeing ports 8000 and 7860 (if in use)...
for %%P in (8000 7860) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr :%%P ^| findstr LISTENING') do (
    taskkill /PID %%I /F >nul 2>nul
  )
)

echo [3/4] Starting backend...
start "" /B cmd /c "cd /d ""%~dp0"" && set PYTHONIOENCODING=utf-8 && py -3.12 -m uvicorn app.api:app --host 127.0.0.1 --port 8000 > logs\backend.log 2>&1"

echo Waiting for backend health...
set /a tries=0
set "BACKEND_READY=0"

:wait_backend
set /a tries+=1
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health -TimeoutSec 2; if($r.StatusCode -eq 200){exit 0}else{exit 1} } catch { exit 1 }" >nul 2>nul
if !errorlevel! EQU 0 (
  set "BACKEND_READY=1"
  goto after_wait
)
if !tries! GEQ 120 goto after_wait
timeout /t 1 >nul
goto wait_backend

:after_wait
if "!BACKEND_READY!"=="1" (
  echo Backend is healthy.
) else (
  echo WARNING: Backend health check timed out. UI will still start.
)

echo [4/4] Starting UI...
start "" /B cmd /c "cd /d ""%~dp0"" && py -3.12 -m streamlit run ui\app.py --server.address 127.0.0.1 --server.port 7860 --browser.gatherUsageStats false > logs\ui.log 2>&1"

echo.
echo Project launched:
echo - Backend health: http://127.0.0.1:8000/health
echo - UI:             http://127.0.0.1:7860
echo - Backend log:    logs\backend.log
echo - UI log:         logs\ui.log
echo.
echo To stop both processes:
echo   for %%P in (8000 7860) do for /f "tokens=5" %%I in ('netstat -ano ^| findstr :%%P ^| findstr LISTENING') do taskkill /PID %%I /F

exit /b 0
